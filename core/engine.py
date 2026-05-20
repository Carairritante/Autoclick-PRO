"""
core/engine.py — Lógica de automação sem UI.

Classes:
  ClickLoop   — loop de cliques em thread separada
  TypeLoop    — loop de digitação em thread separada
  MacroRunner — coordenador; base para macros sequenciais futuros

Sem imports de tkinter. Comunicação com a UI é feita exclusivamente via callbacks.
"""
from __future__ import annotations

import json
import os
import random
import re
import threading
import time
from typing import Callable

import pyautogui

from core.driver import WindowsDriver

# Mapa de tokens especiais no texto de digitação → nomes de teclas do pyautogui
_KEY_TOKEN_MAP: dict[str, str] = {
    "{ENTER}": "enter",       "{TAB}": "tab",         "{UP}": "up",
    "{DOWN}": "down",         "{LEFT}": "left",        "{RIGHT}": "right",
    "{BACKSPACE}": "backspace", "{DELETE}": "delete",
    "{ESCAPE}": "escape",     "{HOME}": "home",        "{END}": "end",
    "{PGUP}": "pageup",       "{PGDN}": "pagedown",    "{SPACE}": "space",
    "{F1}": "f1",   "{F2}": "f2",   "{F3}": "f3",   "{F4}": "f4",
    "{F5}": "f5",   "{F6}": "f6",   "{F7}": "f7",   "{F8}": "f8",
    "{F9}": "f9",   "{F10}": "f10", "{F11}": "f11", "{F12}": "f12",
}


def _parse_type_tokens(text: str) -> list[tuple[str, str]]:
    """Converte texto com tokens especiais em lista de (kind, value).

    kind='char'  → caractere a digitar via pyautogui.write
    kind='key'   → tecla especial a pressionar via pyautogui.press
    """
    tokens: list[tuple[str, str]] = []
    i = 0
    while i < len(text):
        if text[i] == "{":
            end = text.find("}", i)
            if end != -1:
                token = text[i:end + 1].upper()
                if token in _KEY_TOKEN_MAP:
                    tokens.append(("key", _KEY_TOKEN_MAP[token]))
                    i = end + 1
                    continue
        tokens.append(("char", text[i]))
        i += 1
    return tokens


class ClickLoop:
    """Loop de automação de cliques em daemon thread (sem tkinter).

    Uso:
        loop = ClickLoop(driver)
        loop.configure(interval_ms=100, ..., on_click=callback)
        loop.start()
        loop.stop()
    """

    def __init__(self, driver: WindowsDriver) -> None:
        self._driver = driver
        self._running = False
        self._thread: threading.Thread | None = None
        self._seq_index = 0
        self._cfg: dict = {}

        # Callbacks fornecidos pela UI — chamados a partir da thread do loop
        self.on_click: Callable[[], None] | None = None
        self.on_overlay_update: Callable[[int | None, int | None], None] | None = None
        self.on_stop: Callable[[], None] | None = None
        self.on_play_sound: Callable[[], None] | None = None

    def configure(
        self, *,
        interval_ms: int,
        button: str,
        double: bool,
        burst: int,
        pos_mode: str,
        pos_x: int,
        pos_y: int,
        seq_positions: list,
        simultaneous: bool = False,
        target_hwnd: int = 0,
        humanize: bool,
        humanize_pct: float,
        jitter: bool,
        jitter_px: int,
        rep_mode: str,
        rep_count: int,
        sound_enabled: bool,
        on_click: Callable[[], None] | None = None,
        on_overlay_update: Callable[[int | None, int | None], None] | None = None,
        on_stop: Callable[[], None] | None = None,
        on_play_sound: Callable[[], None] | None = None,
    ) -> None:
        """Configura parâmetros do loop. Chame antes de start()."""
        self._cfg = {
            "interval_ms":  interval_ms,
            "button":       button,
            "double":       double,
            "burst":        burst,
            "pos_mode":     pos_mode,
            "pos_x":        pos_x,
            "pos_y":        pos_y,
            "seq_positions": list(seq_positions),
            "simultaneous": simultaneous,
            "target_hwnd":  target_hwnd,
            "humanize":     humanize,
            "humanize_pct": humanize_pct,
            "jitter":       jitter,
            "jitter_px":    jitter_px,
            "rep_mode":     rep_mode,
            "rep_count":    rep_count,
            "sound_enabled": sound_enabled,
        }
        self.on_click         = on_click
        self.on_overlay_update = on_overlay_update
        self.on_stop          = on_stop
        self.on_play_sound    = on_play_sound

    def start(self) -> None:
        """Inicia o loop em daemon thread."""
        self._running = True
        self._seq_index = 0
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Sinaliza o loop para parar na próxima iteração."""
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def _loop(self) -> None:
        cfg = self._cfg
        limit: int | None = None
        if cfg["rep_mode"] == "count":
            limit = max(1, cfg["rep_count"])
        count = 0

        while self._running:
            if limit is not None and count >= limit:
                if self.on_stop:
                    self.on_stop()
                self._running = False
                break

            # Failsafe: mover mouse para (0, 0) interrompe o loop
            try:
                fx, fy = self._driver.get_position()
                if fx == 0 and fy == 0:
                    if self.on_stop:
                        self.on_stop()
                    self._running = False
                    break
            except Exception:
                pass

            # Intervalo com humanização (variação aleatória de ±pct%)
            base_ms: int = cfg["interval_ms"]
            if cfg["humanize"]:
                pct = cfg["humanize_pct"] / 100
                delta = base_ms * pct
                actual_ms = max(0.0, random.uniform(base_ms - delta, base_ms + delta))
            else:
                actual_ms = float(base_ms)

            # Determinar posição do clique
            cx: int | None = None
            cy: int | None = None
            extra_ms = 0.0

            # Modo simultâneo: envia PostMessage para TODOS os pontos sem mover o mouse
            if (cfg["simultaneous"]
                    and cfg["pos_mode"] == "sequence"
                    and cfg["seq_positions"]):
                for pos in cfg["seq_positions"]:
                    self._driver.perform_click_virtual(
                        pos["x"], pos["y"],
                        button=cfg["button"],
                        double=cfg["double"],
                        burst=cfg["burst"],
                    )
            else:
                if cfg["pos_mode"] == "sequence" and cfg["seq_positions"]:
                    pos = cfg["seq_positions"][self._seq_index % len(cfg["seq_positions"])]
                    cx, cy = pos["x"], pos["y"]
                    extra_ms = float(pos.get("delay_ms", 0))
                    self._seq_index += 1
                elif cfg["pos_mode"] == "fixed":
                    cx = cfg["pos_x"]
                    cy = cfg["pos_y"]
                    if cfg["jitter"]:
                        px = cfg["jitter_px"]
                        cx += random.randint(-px, px)
                        cy += random.randint(-px, px)

                # Modo "posição atual do cursor": cx fica None — NÃO movemos o cursor
                # (SendInput com só down/up usa a posição atual automaticamente).
                # Movê-lo causaria drift acumulado: pixel→0-65535→pixel tem erro de
                # arredondamento por divisão inteira, deslocando o cursor 1-2px por clique.
                is_cursor_mode = (cx is None)

                # Pegar posição real só pra overlay/target_hwnd, sem usar pra mover
                if is_cursor_mode:
                    try:
                        cx, cy = self._driver.get_position()
                    except Exception:
                        pass

                # Notificar UI para mover overlay (thread-safe via self.after no callback)
                if self.on_overlay_update and cx is not None:
                    self.on_overlay_update(cx, cy)

                # Executar clique — janela específica usa PostMessage; senão SendInput direto
                hwnd = cfg["target_hwnd"]
                if hwnd and cx is not None:
                    self._driver.perform_click_to_hwnd(
                        hwnd, cx, cy,
                        button=cfg["button"],
                        double=cfg["double"],
                        burst=cfg["burst"],
                    )
                else:
                    # Em modo cursor, passa None pra não mover (evita drift)
                    self._driver.perform_click(
                        None if is_cursor_mode else cx,
                        None if is_cursor_mode else cy,
                        button=cfg["button"],
                        double=cfg["double"],
                        burst=cfg["burst"],
                    )

            if self.on_click:
                self.on_click()

            if cfg["sound_enabled"] and actual_ms >= 50:
                if self.on_play_sound:
                    self.on_play_sound()

            count += 1
            sleep_s = (actual_ms + extra_ms) / 1000
            if sleep_s > 0:
                time.sleep(sleep_s)


class TypeLoop:
    """Loop de digitação automática em daemon thread (sem tkinter).

    Uso:
        loop = TypeLoop(driver)
        loop.configure(text="Olá {ENTER}", interval_ms=50, ...)
        loop.start()
        loop.stop()
    """

    def __init__(self, driver: WindowsDriver) -> None:
        self._driver = driver
        self._running = False
        self._thread: threading.Thread | None = None
        self._cfg: dict = {}

        # Callbacks fornecidos pela UI
        self.on_status: Callable[[str], None] | None = None
        self.on_stop: Callable[[], None] | None = None

    def configure(
        self, *,
        text: str,
        interval_ms: int,
        interval_max_ms: int = 0,
        rep_mode: str,
        rep_count: int,
        delay_s: float,
        paste_mode: bool = False,
        press_enter: bool = False,
        on_status: Callable[[str], None] | None = None,
        on_stop: Callable[[], None] | None = None,
    ) -> None:
        """Configura parâmetros do loop. Chame antes de start()."""
        self._cfg = {
            "text":            text,
            "interval_ms":     interval_ms,
            "interval_max_ms": interval_max_ms if interval_max_ms > interval_ms else interval_ms,
            "rep_mode":        rep_mode,
            "rep_count":       rep_count,
            "delay_s":         delay_s,
            "paste_mode":      paste_mode,
            "press_enter":     press_enter,
        }
        self.on_status = on_status
        self.on_stop   = on_stop

    def start(self) -> None:
        """Inicia o loop em daemon thread."""
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Sinaliza o loop para parar na próxima iteração."""
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def _loop(self) -> None:
        cfg = self._cfg
        delay = cfg["delay_s"]

        if self.on_status:
            self.on_status(f"⏳  Iniciando em {delay:.0f}s...")
        # Sleep em pedaços de 100ms para responder rápido ao Stop, em vez de
        # ficar travado o delay inteiro (até 30s+) ignorando cancelamento.
        deadline = time.monotonic() + delay
        while self._running and time.monotonic() < deadline:
            time.sleep(min(0.1, deadline - time.monotonic()))

        if not self._running:
            return

        tokens = _parse_type_tokens(cfg["text"])
        interval_min_s = cfg["interval_ms"] / 1000
        interval_max_s = cfg["interval_max_ms"] / 1000
        paste_mode     = cfg.get("paste_mode", False)

        def _rand_interval() -> float:
            return random.uniform(interval_min_s, interval_max_s)

        max_reps: int | None = None
        if cfg["rep_mode"] == "count":
            max_reps = max(1, cfg["rep_count"])

        count = 0

        while self._running:
            if max_reps is not None and count >= max_reps:
                if self.on_stop:
                    self.on_stop()
                self._running = False
                break
            if self.on_status:
                if max_reps is not None:
                    self.on_status(f"⌨  Repetição {count + 1}/{max_reps}")
                else:
                    self.on_status(f"⌨  Repetição {count + 1}")
            try:
                if paste_mode:
                    self._run_paste(tokens, _rand_interval)
                else:
                    for kind, value in tokens:
                        if not self._running:
                            break
                        self._driver.perform_type(kind, value)
                        time.sleep(_rand_interval())
                if self._running and cfg.get("press_enter"):
                    self._driver.perform_type("key", "enter")
            except pyautogui.FailSafeException:
                if self.on_stop:
                    self.on_stop()
                self._running = False
                break
            except Exception as exc:
                if self.on_status:
                    self.on_status(f"Erro: {exc}")
                if self.on_stop:
                    self.on_stop()
                self._running = False
                break
            count += 1

    def _run_paste(self, tokens: list[tuple[str, str]], get_interval: Callable[[], float]) -> None:
        """Agrupa runs de chars consecutivos e cola via Ctrl+V; tokens 'key' viram tecla."""
        buf: list[str] = []
        for kind, value in tokens:
            if not self._running:
                break
            if kind == "char":
                buf.append(value)
            else:
                # Flush buffer pendente antes de pressionar tecla especial
                if buf:
                    self._paste_chunk("".join(buf))
                    buf.clear()
                self._driver.perform_type("key", value)
                time.sleep(get_interval())
        if buf and self._running:
            self._paste_chunk("".join(buf))

    def _paste_chunk(self, text: str) -> None:
        """Coloca texto no clipboard e dispara Ctrl+V."""
        if not text:
            return
        if not self._driver.set_clipboard_text(text):
            # Fallback: digita caractere por caractere
            for ch in text:
                if not self._running:
                    return
                self._driver.perform_type("char", ch)
            return
        time.sleep(0.03)  # pequeno delay para o clipboard "assentar"
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.05)  # tempo do app processar o paste


class MacroContext:
    """Estado mutável compartilhado durante a execução de um macro.

    Permite que steps comuniquem entre si: variáveis nomeadas, última imagem
    encontrada (pra offsets/clicks relativos), texto OCR mais recente, fila de
    matches (pra find-all). Persiste durante todo o `_run()` — resetado em cada
    chamada a `start()`.
    """

    def __init__(self) -> None:
        self.variables: dict[str, str | int | float] = {}
        self.last_match: tuple[int, int, int, int] | None = None  # (x,y,w,h)
        self.last_ocr_text: str = ""
        self.matches_queue: list = []
        # Pilha de branch para if/else/endif — cada item: "exec" | "skip" | "skip_nested"
        # Vazia = fluxo normal. Vê _execute_step / docstring no plano.
        self.branch_stack: list[str] = []
        # call_macro: caminhos absolutos dos macros em execução (detecta ciclo)
        self.call_stack: set[str] = set()


class SequentialRunner:
    """Executa uma lista de MacroSteps em sequência em daemon thread."""

    # Cap pra evitar crescimento ilimitado se um macro chama muitos sub-macros
    # diferentes ao longo do tempo. 32 cobre cenários reais com folga.
    _MACRO_CACHE_MAX = 32

    def __init__(self, driver: WindowsDriver) -> None:
        self._driver  = driver
        self._running = False
        self._thread: threading.Thread | None = None
        self._step_event: threading.Event | None = None
        self._on_variable_change: Callable[[str, object], None] | None = None
        # Pausa cooperativa — checada entre steps
        self._paused = False
        self._pause_cond = threading.Condition()
        # Cache de sub-macros (call_macro): path → (mtime, steps).
        # Evita re-ler+parsear JSON a cada chamada num loop. Invalida quando
        # o arquivo é modificado em disco (compara mtime). Capped a _MACRO_CACHE_MAX.
        self._macro_cache: dict[str, tuple[float, list]] = {}

    def start(
        self,
        steps: list,
        repeat_count: int | None,
        loop_delay_ms: int,
        on_step: Callable[[int], None] | None,
        on_stop: Callable[[], None] | None,
        target_hwnd: int = 0,
        speed: float = 1.0,
        step_event: threading.Event | None = None,
        on_variable_change: Callable[[str, object], None] | None = None,
        stop_conditions: list | None = None,
        on_stop_condition: Callable[[str], None] | None = None,
    ) -> None:
        self._running = True
        # Reset estado de pausa: se uma execução anterior foi interrompida
        # com _paused=True (ex: app fechado durante pause), sem isso a nova
        # execução entraria em wait infinito no primeiro check de pause.
        self._paused = False
        self._step_event = step_event
        self._on_variable_change = on_variable_change
        self._thread = threading.Thread(
            target=self._run,
            args=(steps, repeat_count, loop_delay_ms, on_step, on_stop,
                  target_hwnd, speed, step_event,
                  stop_conditions or [], on_stop_condition),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self.resume()  # garante que sai do wait se estava pausado
        if self._step_event is not None:
            self._step_event.set()  # desbloqueia se pausado em debug mode

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        with self._pause_cond:
            self._paused = False
            self._pause_cond.notify_all()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    def _run(
        self,
        steps: list,
        repeat_count: int | None,
        loop_delay_ms: int,
        on_step: Callable[[int], None] | None,
        on_stop: Callable[[], None] | None,
        target_hwnd: int = 0,
        speed: float = 1.0,
        step_event: threading.Event | None = None,
        stop_conditions: list | None = None,
        on_stop_condition: Callable[[str], None] | None = None,
    ) -> None:
        loops = 0
        spd = max(0.1, speed)
        ctx = MacroContext()
        # Mínimo de 1ms entre loops — sem isso, macros muito rápidos em jogos
        # (Roblox em particular) saturam o input queue e travam a janela.
        # Defesa em profundidade: a UI também aplica esse mínimo no spinbox.
        effective_loop_delay = max(1, loop_delay_ms)
        while self._running:
            if repeat_count is not None and loops >= repeat_count:
                break
            # Reset branch stack a cada iteração: garante consistência se o macro
            # tem if mal-balanceado, não deixa estado vazar entre loops
            ctx.branch_stack = []
            self._run_steps(steps, ctx, target_hwnd, spd,
                            step_event=step_event, on_step=on_step,
                            stop_conditions=stop_conditions or [],
                            on_stop_condition=on_stop_condition)
            if self._running:
                time.sleep(effective_loop_delay / spd / 1000)
            loops += 1
        self._running = False
        if on_stop:
            on_stop()

    def _run_steps(
        self,
        steps: list,
        ctx: MacroContext,
        target_hwnd: int,
        spd: float,
        step_event: threading.Event | None = None,
        on_step: Callable[[int], None] | None = None,
        stop_conditions: list | None = None,
        on_stop_condition: Callable[[str], None] | None = None,
    ) -> None:
        """Executa uma lista de steps. Reutilizável por call_macro (recursivo)."""
        i = 0
        while i < len(steps) and self._running:
            # Pausa cooperativa — checada entre steps, não interrompe step em execução
            if self._paused:
                with self._pause_cond:
                    while self._paused and self._running:
                        self._pause_cond.wait(timeout=0.1)
                if not self._running:
                    break

            # Stop conditions são checadas ANTES de cada step
            if stop_conditions:
                triggered = self._check_stop_conditions(stop_conditions, ctx)
                if triggered is not None:
                    if on_stop_condition:
                        try: on_stop_condition(triggered)
                        except Exception: pass
                    self._running = False
                    break

            step = steps[i]
            # Para wait, delay_ms É o tempo de espera; para os demais é pré-delay
            if step.action == "wait":
                # wait também respeita branch (não dorme se está pulando)
                is_skipping = any(s in ("skip", "skip_nested") for s in ctx.branch_stack)
                if not is_skipping:
                    time.sleep(step.delay_ms / spd / 1000)
                skip = 0
            else:
                # Pré-delay só se NÃO estamos pulando (se/else/endif sempre processam)
                is_skipping = any(s in ("skip", "skip_nested") for s in ctx.branch_stack)
                if step.delay_ms > 0 and not is_skipping and step.action not in ("if", "else", "endif"):
                    time.sleep(step.delay_ms / spd / 1000)
                if not self._running:
                    break
                skip = self._execute_step(step, ctx, target_hwnd, spd)
            if on_step:
                on_step(i)
            # Step-by-step debug: aguarda sinal da UI para avançar
            if step_event is not None and self._running:
                step_event.wait()
                step_event.clear()
                if not self._running:
                    break
            i += 1 + skip

    def _resolve_var_value(self, value: str, ctx: MacroContext) -> str:
        """Substitui {nome} pelos valores das variáveis. Retorna a string final."""
        if not value or "{" not in value:
            return value
        def repl(m: "re.Match") -> str:
            v = ctx.variables.get(m.group(1), "")
            return str(v)
        return re.sub(r"\{(\w+)\}", repl, value)

    def _notify_var(self, name: str, value: object) -> None:
        if self._on_variable_change:
            try:
                self._on_variable_change(name, value)
            except Exception:
                pass

    def _click_via_target(self, x: int, y: int, button: str, double: bool,
                          target_hwnd: int) -> None:
        """Dispara clique respeitando janela-alvo: PostMessage se setada, senão SendInput."""
        if target_hwnd:
            self._driver.perform_click_to_hwnd(
                target_hwnd, x, y, button=button, double=double)
        else:
            self._driver.perform_click(x, y, button=button, double=double)

    def _compare(self, left, right, op: str) -> bool:
        """Compara dois valores. Tenta numérico, fallback pra string."""
        try:
            ln, rn = float(left), float(right)
            if op == "==": return ln == rn
            if op == "!=": return ln != rn
            if op == "<":  return ln < rn
            if op == ">":  return ln > rn
            if op == "<=": return ln <= rn
            if op == ">=": return ln >= rn
        except (ValueError, TypeError):
            pass
        ls, rs = str(left), str(right)
        if op == "==":          return ls == rs
        if op == "!=":          return ls != rs
        if op == "contains":    return rs in ls
        if op == "starts_with": return ls.startswith(rs)
        if op == "<":           return ls < rs
        if op == ">":           return ls > rs
        if op == "<=":          return ls <= rs
        if op == ">=":          return ls >= rs
        return False

    def _eval_condition(self, step, ctx: MacroContext, target_hwnd: int) -> bool:
        """Avalia uma condição (cond_type=var/image/pixel). Retorna True/False."""
        cond_type = step.cond_type or "var"
        if cond_type == "var":
            left = ctx.variables.get(step.var_name, "")
            right = self._resolve_var_value(step.cond_value, ctx)
            return self._compare(left, right, step.cond_op or "==")
        if cond_type == "image":
            # `if image present` é snapshot — queremos saber se a imagem está
            # AGORA na tela, não esperar até `image_timeout_ms` ela aparecer.
            # Pra esperar, o usuário usa wait_image antes do if.
            found = self._driver.find_image_on_screen(
                step.image_data,
                threshold=step.image_threshold or 0.9,
                timeout_ms=0,
            )
            if found:
                ctx.last_match = found
            present = found is not None
            return present if (step.cond_op or "present") == "present" else (not present)
        if cond_type == "pixel":
            if step.color_rgb and len(step.color_rgb) == 3 and step.x is not None and step.y is not None:
                r, g, b = self._driver.get_pixel_color(step.x, step.y)
                tr, tg, tb = step.color_rgb
                tol = step.color_tolerance
                matched = (abs(r - tr) <= tol and abs(g - tg) <= tol and abs(b - tb) <= tol)
                return matched if (step.cond_op or "match") == "match" else (not matched)
        return False

    def _check_stop_conditions(self, stop_conditions: list, ctx: MacroContext) -> str | None:
        """Itera stop conditions. Retorna label da primeira que disparar, ou None.

        Stop conditions de IMAGEM são caras (locateOnScreen + OpenCV) — checadas
        no máximo a cada 250ms para não estrangular macros longos. Pixel/var são
        baratas e checadas a cada step.
        """
        now = time.monotonic()
        # Throttle só nas conditions de imagem; primeira chamada sempre roda.
        do_image = (now - getattr(ctx, "_last_img_cond_t", 0.0)) >= 0.25
        for sc in stop_conditions:
            if not getattr(sc, "enabled", True):
                continue
            try:
                t = getattr(sc, "type", "image")
                if t == "image" and sc.image_data:
                    if not do_image:
                        continue
                    if self._driver.find_image_on_screen(sc.image_data, sc.image_threshold):
                        return sc.label or "image detectada"
                elif t == "pixel" and sc.color_rgb and sc.x is not None and sc.y is not None:
                    r, g, b = self._driver.get_pixel_color(sc.x, sc.y)
                    tr, tg, tb = sc.color_rgb
                    tol = sc.color_tolerance
                    if (abs(r-tr) <= tol and abs(g-tg) <= tol and abs(b-tb) <= tol):
                        return sc.label or "pixel match"
                elif t == "var" and sc.var_name:
                    left = ctx.variables.get(sc.var_name, "")
                    right = self._resolve_var_value(sc.var_value, ctx)
                    if self._compare(left, right, sc.var_op or "=="):
                        return sc.label or f"{sc.var_name} {sc.var_op} {sc.var_value}"
            except Exception:
                pass
        if do_image:
            ctx._last_img_cond_t = now
        return None

    def _execute_step(self, step, ctx: MacroContext, target_hwnd: int = 0,
                       spd: float = 1.0) -> int:
        """Executa um único MacroStep via WindowsDriver. Retorna quantos steps pular."""
        action = step.action
        n = max(1, step.repeat)

        # ── Controle de fluxo if/else/endif: SEMPRE processado, mesmo em skip ──
        if action == "if":
            is_skipping = any(s in ("skip", "skip_nested") for s in ctx.branch_stack)
            if is_skipping:
                ctx.branch_stack.append("skip_nested")
            else:
                result = self._eval_condition(step, ctx, target_hwnd)
                ctx.branch_stack.append("exec" if result else "skip")
            return 0
        if action == "else":
            if ctx.branch_stack and ctx.branch_stack[-1] != "skip_nested":
                ctx.branch_stack[-1] = "skip" if ctx.branch_stack[-1] == "exec" else "exec"
            return 0
        if action == "endif":
            if ctx.branch_stack:
                ctx.branch_stack.pop()
            return 0

        # ── Steps normais: pulados se estamos em branch falso ────────────────
        if any(s in ("skip", "skip_nested") for s in ctx.branch_stack):
            return 0

        # Resolver coordenadas relativas → absolutas quando janela-alvo disponível
        x, y = step.x, step.y
        if target_hwnd and step.rel_x is not None and step.rel_y is not None:
            rect = self._driver.get_window_rect(target_hwnd)
            if rect:
                left, top, w, h = rect
                x = int(left + step.rel_x * w)
                y = int(top  + step.rel_y * h)

        if action in ("click", "double_click", "right_click"):
            double = (action == "double_click")
            btn = "right" if action == "right_click" else step.button
            for _ in range(n):
                if not self._running:
                    break
                self._click_via_target(x, y, btn, double, target_hwnd)
        elif action == "move":
            if x is not None and y is not None:
                self._driver.perform_move(x, y)
        elif action == "type":
            if step.text:
                resolved = self._resolve_var_value(step.text, ctx)
                tokens = _parse_type_tokens(resolved)
                # Texto longo PURO (sem tokens especiais) → paste mode:
                # instantâneo, evita auto-format de WhatsApp/Discord engasgar.
                only_chars = all(k == "char" for k, _ in tokens)
                if only_chars and len(resolved) > 20:
                    if self._driver.paste_text(resolved):
                        return 0
                    # Clipboard falhou — cai pra digitação tradicional
                for kind, value in tokens:
                    if not self._running:
                        break
                    self._driver.perform_type(kind, value)
        elif action == "scroll":
            for _ in range(n):
                if not self._running:
                    break
                self._driver.perform_scroll(
                    x, y, dy=step.scroll_dy,
                    smooth=getattr(step, "scroll_smooth", False),
                )
        elif action == "drag":
            if x is not None and y is not None and step.x2 is not None and step.y2 is not None:
                x2, y2 = step.x2, step.y2
                # Coords relativas → absolutas quando há janela-alvo
                if target_hwnd and step.rel_x2 is not None and step.rel_y2 is not None:
                    rect = self._driver.get_window_rect(target_hwnd)
                    if rect:
                        left, top, w, h = rect
                        x2 = int(left + step.rel_x2 * w)
                        y2 = int(top  + step.rel_y2 * h)
                self._driver.perform_drag(
                    x, y, x2, y2,
                    duration_ms=max(50, step.drag_duration_ms),
                    button=step.button,
                )
        elif action == "wait_image":
            if step.image_data:
                # monotonic: imune a mudanças do relógio do sistema (NTP/DST)
                deadline = time.monotonic() + (step.image_timeout_ms or 5000) / 1000 / spd
                want_present = (step.image_wait_for or "present") == "present"
                while self._running and time.monotonic() < deadline:
                    # Respeita pausa cooperativa também aqui — wait_image pode
                    # rodar por 30s+, não pode ignorar pause esse tempo todo.
                    if self._paused:
                        pause_start = time.monotonic()
                        with self._pause_cond:
                            while self._paused and self._running:
                                self._pause_cond.wait(timeout=0.1)
                        if not self._running:
                            break
                        # Estende o deadline pelo tempo pausado: se o usuário
                        # pausa por 10s, o timeout não conta esse tempo. Sem
                        # isso, pausa longa = timeout zerado ao retomar.
                        deadline += time.monotonic() - pause_start
                        continue
                    found = self._driver.find_image_on_screen(
                        step.image_data, step.image_threshold,
                    )
                    present = found is not None
                    if present == want_present:
                        if found:
                            ctx.last_match = found
                        break
                    # 200ms = ~5 OpenCV matches/s, suficiente pra UX e metade
                    # do custo de CPU vs polling 100ms anterior
                    time.sleep(0.2)
        elif action == "wait_pixel":
            # Polling rápido de UM pixel via GDI (~0.1ms/chamada). A 200Hz
            # (5ms entre samples) a janela de reação é <10ms — suficiente
            # pra skill checks de Roblox (janela típica 50-150ms).
            # Reusa campos color_rgb/color_tolerance (do pixel_check) +
            # image_timeout_ms/image_wait_for/image_skip_steps (do wait_image).
            if (step.color_rgb and len(step.color_rgb) == 3
                    and x is not None and y is not None):
                deadline = time.monotonic() + (step.image_timeout_ms or 5000) / 1000 / spd
                want_match = (step.image_wait_for or "present") == "present"
                tr, tg, tb = step.color_rgb
                tol = step.color_tolerance
                matched = False
                while self._running and time.monotonic() < deadline:
                    if self._paused:
                        pause_start = time.monotonic()
                        with self._pause_cond:
                            while self._paused and self._running:
                                self._pause_cond.wait(timeout=0.1)
                        if not self._running:
                            break
                        deadline += time.monotonic() - pause_start
                        continue
                    try:
                        r, g, b = self._driver.get_pixel_color(x, y)
                    except Exception:
                        time.sleep(0.005)
                        continue
                    is_match = (abs(r - tr) <= tol
                                and abs(g - tg) <= tol
                                and abs(b - tb) <= tol)
                    if is_match == want_match:
                        matched = True
                        break
                    time.sleep(0.005)  # 5ms = 200Hz polling
                if not matched:
                    # Timeout sem match — pula N steps (igual image_click/wait_image)
                    return step.image_skip_steps
        elif action == "call_macro":
            target = self._resolve_macro_target(step.call_target_kind, step.call_target)
            if target is None:
                return 0  # macro não encontrado — silenciosamente continua
            if target in ctx.call_stack:
                return 0  # ciclo detectado — silenciosamente skip
            ctx.call_stack.add(target)
            # Isola branch_stack: sub-macro tem seu próprio espaço de if/else,
            # se ele tem if mal-balanceado não contamina o macro chamador.
            saved_branch = ctx.branch_stack
            ctx.branch_stack = []
            try:
                sub_steps = self._load_macro_steps(target)
                # Reutiliza o mesmo ctx: variáveis compartilhadas entre macros
                self._run_steps(sub_steps, ctx, target_hwnd, spd)
            finally:
                ctx.branch_stack = saved_branch
                ctx.call_stack.discard(target)
        elif action == "key_press":
            if step.key:
                for _ in range(n):
                    if not self._running:
                        break
                    self._driver.perform_type("key", step.key)
        elif action == "pixel_check":
            if step.color_rgb and len(step.color_rgb) == 3 and x is not None and y is not None:
                r, g, b = self._driver.get_pixel_color(x, y)
                tr, tg, tb = step.color_rgb
                tol = step.color_tolerance
                matched = (abs(r - tr) <= tol and abs(g - tg) <= tol and abs(b - tb) <= tol)
                should_skip = (
                    (step.color_condition == "match"    and matched) or
                    (step.color_condition == "no_match" and not matched)
                )
                return step.skip_steps if should_skip else 0
        elif action == "image_click":
            if step.image_data:
                # Usa o helper centralizado do driver — diagnostica opencv ausente
                # com erro claro em vez de silenciosamente "não achar" a imagem
                found_box = self._driver.find_image_on_screen(
                    step.image_data,
                    threshold=step.image_threshold,
                    timeout_ms=step.image_timeout_ms,
                )
                if found_box:
                    left, top, w, h = found_box
                    cx = left + w // 2
                    cy = top + h // 2
                    ctx.last_match = found_box
                    self._click_via_target(cx, cy, "left", False, target_hwnd)
                else:
                    return step.image_skip_steps
        elif action == "click_text":
            if step.text_to_find:
                region = None
                if step.text_use_region and step.ocr_w > 0 and step.ocr_h > 0 \
                        and x is not None and y is not None:
                    region = (x, y, step.ocr_w, step.ocr_h)
                found_box = self._driver.find_text_on_screen(
                    text=step.text_to_find,
                    region=region,
                    match_mode=step.text_match_mode or "contains",
                    case_sensitive=step.text_case_sensitive,
                    lang=step.ocr_lang or "eng",
                )
                if found_box:
                    left, top, w, h = found_box
                    cx = left + w // 2
                    cy = top + h // 2
                    ctx.last_match = found_box
                    self._click_via_target(cx, cy, "left", False, target_hwnd)
                else:
                    return step.text_skip_steps
        elif action == "ocr_read":
            if step.ocr_w > 0 and step.ocr_h > 0 and x is not None and y is not None and step.ocr_var:
                img = self._driver.capture_region(x, y, step.ocr_w, step.ocr_h)
                text = self._driver.run_ocr(img, step.ocr_lang or "eng", step.ocr_whitelist)
                ctx.last_ocr_text = text
                if step.ocr_to_number:
                    try:
                        # Pega o primeiro número válido na string (Tesseract pode adicionar \n)
                        m = re.search(r"-?\d+(?:\.\d+)?", text)
                        if m:
                            val = float(m.group(0))
                            ctx.variables[step.ocr_var] = int(val) if val.is_integer() else val
                        else:
                            ctx.variables[step.ocr_var] = 0
                    except (ValueError, TypeError):
                        ctx.variables[step.ocr_var] = 0
                else:
                    ctx.variables[step.ocr_var] = text
                self._notify_var(step.ocr_var, ctx.variables[step.ocr_var])
        elif action == "clipboard_set":
            # Coloca texto no clipboard. Aceita {var} pra interpolar variáveis.
            resolved = self._resolve_var_value(step.var_value or "", ctx)
            self._driver.set_clipboard_text(str(resolved))
        elif action == "clipboard_get":
            # Lê o clipboard e salva em ctx.variables[var_name]. Sem var_name = no-op.
            if step.var_name:
                text = self._driver.get_clipboard_text() or ""
                ctx.variables[step.var_name] = text
                self._notify_var(step.var_name, text)
        elif action == "wait_window":
            # Polling pelo título da janela até timeout. Pausa cooperativa respeitada.
            if step.window_title:
                from ui.window_picker import list_visible_windows
                target = step.window_title.lower()
                # monotonic: imune a mudanças do relógio do sistema (NTP/DST)
                deadline = time.monotonic() + (step.window_timeout_ms or 5000) / 1000 / spd
                while self._running and time.monotonic() < deadline:
                    if self._paused:
                        pause_start = time.monotonic()
                        with self._pause_cond:
                            while self._paused and self._running:
                                self._pause_cond.wait(timeout=0.1)
                        if not self._running:
                            break
                        deadline += time.monotonic() - pause_start
                        continue
                    try:
                        windows = list_visible_windows()
                    except Exception:
                        windows = []
                    if any(target in title.lower() for _, title in windows):
                        break
                    time.sleep(0.3)
        elif action == "http_request":
            self._do_http_request(step, ctx)
        elif action == "set_var":
            if step.var_name:
                resolved = self._resolve_var_value(step.var_value, ctx)
                op = step.var_op or "set"
                if op == "set":
                    # Tenta armazenar como número se aplicável (facilita ops posteriores)
                    try:
                        f = float(resolved)
                        ctx.variables[step.var_name] = int(f) if f.is_integer() else f
                    except (ValueError, TypeError):
                        ctx.variables[step.var_name] = resolved
                elif op == "concat":
                    current = ctx.variables.get(step.var_name, "")
                    ctx.variables[step.var_name] = f"{current}{resolved}"
                elif op == "from_clipboard":
                    ctx.variables[step.var_name] = self._driver.get_clipboard_text()
                elif op == "to_clipboard":
                    self._driver.set_clipboard_text(str(resolved))
                else:
                    current = ctx.variables.get(step.var_name, 0)
                    try:
                        cur_n = float(current)
                        val_n = float(resolved)
                        if op == "add":   result = cur_n + val_n
                        elif op == "sub": result = cur_n - val_n
                        elif op == "mul": result = cur_n * val_n
                        elif op == "div":
                            result = cur_n / val_n if val_n != 0 else cur_n
                        else: result = cur_n
                        ctx.variables[step.var_name] = int(result) if float(result).is_integer() else result
                    except (ValueError, TypeError):
                        pass  # operação aritmética em string não-numérica → ignora
                self._notify_var(step.var_name, ctx.variables.get(step.var_name))
        return 0

    # ── Helper para http_request ─────────────────────────────────────────────
    def _do_http_request(self, step, ctx: MacroContext) -> None:
        """Executa step http_request: HTTP via requests, salva resposta em var.

        Interpola {var} em URL/body/headers/auth_value. Erros de rede são
        silenciosos no macro (pra não derrubar loop); usuário pode opcionalmente
        checar http_save_status_var (-1 quando timeout/conexão falha).
        """
        if not step.http_url:
            return
        try:
            import requests
        except ImportError:
            return  # requests deveria estar presente (vem com ntfy), mas defensivo
        url = self._resolve_var_value(step.http_url, ctx)
        body = self._resolve_var_value(step.http_body, ctx) if step.http_body else None
        # Parse headers "Key: Value" linha por linha
        headers: dict[str, str] = {}
        for line in (step.http_headers or "").splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                headers[k.strip()] = self._resolve_var_value(v.strip(), ctx)
        # Content-Type default se tem body e usuário não definiu
        if body and not any(h.lower() == "content-type" for h in headers):
            headers["Content-Type"] = "application/json"
        # Auth
        auth = None
        if step.http_auth_kind == "bearer" and step.http_auth_value:
            tok = self._resolve_var_value(step.http_auth_value, ctx)
            headers["Authorization"] = f"Bearer {tok}"
        elif step.http_auth_kind == "basic" and step.http_auth_value:
            creds = self._resolve_var_value(step.http_auth_value, ctx)
            if ":" in creds:
                user, _, pwd = creds.partition(":")
                auth = (user, pwd)
        # Request
        try:
            r = requests.request(
                (step.http_method or "POST").upper(),
                url,
                data=body.encode("utf-8") if body else None,
                headers=headers,
                auth=auth,
                timeout=max(1, step.http_timeout_s or 10),
            )
            if step.var_name:
                ctx.variables[step.var_name] = r.text
                self._notify_var(step.var_name, r.text)
            if step.http_save_status_var:
                ctx.variables[step.http_save_status_var] = r.status_code
                self._notify_var(step.http_save_status_var, r.status_code)
        except Exception:
            # Timeout/conexão/etc: status -1 sinaliza falha se usuário quer saber
            if step.http_save_status_var:
                ctx.variables[step.http_save_status_var] = -1
                self._notify_var(step.http_save_status_var, -1)

    # ── Helpers para call_macro ──────────────────────────────────────────────
    def _resolve_macro_target(self, kind: str, target: str) -> str | None:
        """Converte (kind, target) em caminho absoluto. Retorna None se inválido."""
        from core.paths import PROFILES_DIR
        if kind == "slot":
            try:
                slot = int(target)
                path = os.path.join(PROFILES_DIR, f"slot{slot}.json")
                return path if os.path.exists(path) else None
            except ValueError:
                return None
        return target if target and os.path.exists(target) else None

    def _load_macro_steps(self, path: str) -> list:
        """Carrega e deserializa MacroSteps de um arquivo .json de perfil.

        Usa cache por (path, mtime) — chamadas seguidas no mesmo arquivo
        retornam direto sem tocar disco. Invalidação automática se o arquivo
        muda em disco entre chamadas (mtime difere).
        """
        from core.macro_schema import script_from_dict, macrostep_from_dict
        try:
            mtime = os.path.getmtime(path)
            cached = self._macro_cache.get(path)
            if cached and cached[0] == mtime:
                return cached[1]
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            script = script_from_dict(data)
            steps = [macrostep_from_dict(d) for d in script.macro_steps]
            # Evict mais antigo se atingir o cap (FIFO, suficiente pra esse caso)
            if len(self._macro_cache) >= self._MACRO_CACHE_MAX:
                oldest = next(iter(self._macro_cache))
                self._macro_cache.pop(oldest, None)
            self._macro_cache[path] = (mtime, steps)
            return steps
        except (OSError, KeyError, TypeError, ValueError):
            # ValueError já cobre json.JSONDecodeError (subclasse)
            return []


class MacroRunner:
    """Coordenador de ClickLoop, TypeLoop e SequentialRunner."""

    def __init__(self, driver: WindowsDriver) -> None:
        self._driver     = driver
        self._click_loop = ClickLoop(driver)
        self._type_loop  = TypeLoop(driver)
        self._seq_runner = SequentialRunner(driver)

    def get_click_loop(self) -> ClickLoop:
        return self._click_loop

    def get_type_loop(self) -> TypeLoop:
        return self._type_loop

    def get_sequential_runner(self) -> SequentialRunner:
        return self._seq_runner

    def stop_all(self) -> None:
        """Para todos os loops imediatamente (sinalização)."""
        self._click_loop.stop()
        self._type_loop.stop()
        self._seq_runner.stop()
