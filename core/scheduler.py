"""
core/scheduler.py — Worker que dispara macros em horários agendados.

Regras suportadas:
  - daily:   roda todo dia em HH:MM
  - weekly:  roda nos dias da semana selecionados em HH:MM
  - once:    roda uma vez em YYYY-MM-DD HH:MM (após disparar, fica disabled)

Cada regra é um dict (serializado em profiles/scheduler.json):
  {
    "id": "uuid",
    "name": "Backup diário",
    "enabled": true,
    "freq": "daily" | "weekly" | "once",
    "time": "HH:MM",                       # daily/weekly
    "weekdays": [0,1,2,3,4],               # weekly only — 0=segunda...6=domingo
    "date": "2026-05-20",                  # once only
    "macro_kind": "slot" | "file",
    "macro_target": "1" | "/path/to.json",
  }

O worker checa a cada 30s. Para evitar dispatch duplo dentro do mesmo
minuto (se checkagem cair 2x na mesma janela HH:MM), usa _last_fired[id].
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable


@dataclass
class ScheduleRule:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    enabled: bool = True
    freq: str = "daily"                       # "daily" | "weekly" | "once"
    time: str = "09:00"                       # HH:MM (daily/weekly)
    weekdays: list = field(default_factory=lambda: [0, 1, 2, 3, 4])   # 0=seg
    date: str = ""                            # YYYY-MM-DD (once)
    macro_kind: str = "slot"                  # "slot" | "file"
    macro_target: str = "1"                   # slot number ou caminho


def rule_from_dict(d: dict) -> ScheduleRule:
    """Aceita dict parcial — campos ausentes usam defaults."""
    known = ScheduleRule.__dataclass_fields__
    return ScheduleRule(**{k: v for k, v in d.items() if k in known})


def rule_to_dict(r: ScheduleRule) -> dict:
    return {
        "id": r.id, "name": r.name, "enabled": r.enabled,
        "freq": r.freq, "time": r.time, "weekdays": list(r.weekdays),
        "date": r.date, "macro_kind": r.macro_kind, "macro_target": r.macro_target,
    }


class SchedulerWorker:
    """Thread daemon que checa regras a cada 30s.

    on_fire(rule) é chamado quando regra dispara — quem implementa decide
    como carregar/rodar o macro (precisa ser thread-safe via app.after).
    """
    CHECK_INTERVAL_S = 30

    def __init__(self) -> None:
        self._rules: list[ScheduleRule] = []
        self._last_fired: dict[str, str] = {}    # id → "YYYY-MM-DD HH:MM" última disparada
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self.on_fire: Callable[[ScheduleRule], None] | None = None

    # ── persistência ────────────────────────────────────────────────────
    def load(self, path: str) -> None:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        rules = data.get("rules", [])
        with self._lock:
            self._rules = [rule_from_dict(r) for r in rules]

    def save(self, path: str) -> None:
        """Atomic write — evita corromper arquivo se app crashar no meio."""
        with self._lock:
            data = {"rules": [rule_to_dict(r) for r in self._rules]}
        tmp = path + ".tmp"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    # ── CRUD ────────────────────────────────────────────────────────────
    def get_all(self) -> list[ScheduleRule]:
        with self._lock:
            return list(self._rules)

    def add(self, rule: ScheduleRule) -> None:
        with self._lock:
            self._rules.append(rule)

    def update(self, rule_id: str, new_rule: ScheduleRule) -> bool:
        with self._lock:
            for i, r in enumerate(self._rules):
                if r.id == rule_id:
                    new_rule.id = rule_id     # preserva id
                    self._rules[i] = new_rule
                    return True
        return False

    def remove(self, rule_id: str) -> bool:
        with self._lock:
            for i, r in enumerate(self._rules):
                if r.id == rule_id:
                    self._rules.pop(i)
                    self._last_fired.pop(rule_id, None)
                    return True
        return False

    def toggle(self, rule_id: str) -> bool:
        with self._lock:
            for r in self._rules:
                if r.id == rule_id:
                    r.enabled = not r.enabled
                    return r.enabled
        return False

    # ── worker loop ─────────────────────────────────────────────────────
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _loop(self) -> None:
        # Pequeno delay inicial pra UI terminar de subir antes de disparar
        time.sleep(2)
        while self._running:
            try:
                self._tick()
            except Exception:
                pass    # nunca derruba o worker
            # Sleep em pequenos pedaços pra responder rápido a stop()
            for _ in range(self.CHECK_INTERVAL_S):
                if not self._running:
                    return
                time.sleep(1)

    def _tick(self) -> None:
        now = datetime.now()
        now_key = now.strftime("%Y-%m-%d %H:%M")
        with self._lock:
            rules = [r for r in self._rules if r.enabled]
        for rule in rules:
            if self._should_fire(rule, now) and self._last_fired.get(rule.id) != now_key:
                self._last_fired[rule.id] = now_key
                if rule.freq == "once":
                    # Auto-desativa após disparar
                    with self._lock:
                        for r in self._rules:
                            if r.id == rule.id:
                                r.enabled = False
                                break
                if self.on_fire:
                    try:
                        self.on_fire(rule)
                    except Exception:
                        pass

    def _should_fire(self, rule: ScheduleRule, now: datetime) -> bool:
        """Retorna True se o horário atual bate exatamente com a regra (HH:MM)."""
        try:
            hh, mm = rule.time.split(":")
            target_h, target_m = int(hh), int(mm)
        except (ValueError, AttributeError):
            return False
        if now.hour != target_h or now.minute != target_m:
            return False
        if rule.freq == "daily":
            return True
        if rule.freq == "weekly":
            # datetime.weekday() já retorna 0=segunda, igual nossa convenção
            return now.weekday() in (rule.weekdays or [])
        if rule.freq == "once":
            today = now.strftime("%Y-%m-%d")
            return rule.date == today
        return False
