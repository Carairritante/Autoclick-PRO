"""
core/ntfy_client.py — Cliente ntfy.sh para alertas/comandos via celular.

ntfy.sh é um serviço público (e open-source) de push notifications via HTTP
pub/sub. Cada usuário tem 1 tópico com nome aleatório:
  - autoclick-{ID}: PC publica alertas/screenshots (taggeados "from-pc") +
    celular publica comandos (sem tag) → PC ignora mensagens com tag "from-pc"
    e processa só as outras como comandos.

Por que 1 tópico só (e não 2): no app ntfy, o usuário só consegue digitar
no tópico que ele assinou (o do QR). Se PC publica em A e escuta em B,
mensagens digitadas pelo usuário vão pra A e nunca chegam ao PC.

Roda 2 threads daemon enquanto ativo:
  1. _subscribe_loop: long-poll HTTP no topic, dispara on_command() pra msgs
     sem a tag "from-pc"
  2. _monitor_loop:   avalia monitores periodicamente, dispara publish()
"""
from __future__ import annotations

import json
import os
import secrets
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Callable


@dataclass
class Monitor:
    """Define um gatilho que dispara notificação ao celular e/ou PC.

    trigger_type:
      - "image": acionado se imagem aparece na tela (find_image_on_screen)
      - "pixel": acionado se pixel (x,y) tem cor color_rgb ± tolerance
      - "text":  acionado se texto aparece via OCR (find_text_on_screen)
      - "event": acionado por evento programático (fire_event), event_name=:
                 macro_started, macro_stopped, macro_stopped_by_cond, hotstring_fired
      - "var":   reservado, ainda não implementado (depende de ctx do macro)
    """
    name: str = ""
    trigger_type: str = "image"          # "image" | "pixel" | "text" | "var" | "event"
    # Imagem (mesmo formato de StopCondition)
    image_data: str | None = None        # PNG base64
    image_threshold: float = 0.9
    # Pixel
    x: int | None = None
    y: int | None = None
    color_rgb: list | None = None
    color_tolerance: int = 10
    # Texto (OCR)
    text_to_find: str = ""
    text_match_mode: str = "contains"    # "contains" | "exact" | "regex"
    text_case_sensitive: bool = False
    text_lang: str = "eng"               # "eng" | "por" | "spa" | etc
    text_min_confidence: int = 50        # 0-100, descarta leituras abaixo
    # Variável (placeholder)
    var_name: str = ""
    var_op: str = "=="
    var_value: str = ""
    # Evento
    event_name: str = ""                 # "macro_started" | "macro_stopped" | etc
    # Mensagem personalizada — vazio = usa f"Disparou: {name}"
    custom_message: str = ""
    # Destino da notificação
    notify_phone: bool = True            # ntfy.sh (celular)
    notify_pc:    bool = True            # bandeja do Windows (pystray.notify)
    # Restrição a janela alvo (image/text usam como região; pixel ignora)
    target_hwnd: int = 0                 # 0 = tela inteira
    target_win_name: str = ""            # só pra UI mostrar
    # Ação
    enabled: bool = True
    cooldown_s: int = 30                 # anti-spam: não dispara 2x no intervalo
    attach_screenshot: bool = False
    # Estado runtime (NÃO persistido — filtrado em save/load)
    _last_fired_t: float = field(default=0.0, repr=False)


class NtfyClient:
    """Cliente ntfy.sh: publish + long-poll subscribe + loop de monitores.

    Lifecycle:
        client = NtfyClient(driver)
        client.load(path)            # restaura topic_id + monitores
        client.on_command = lambda cmd: ...   # set callback ANTES de start
        client.on_status_change = lambda s: ...
        client.start()               # dispara 2 threads daemon
        # ... usuário interage ...
        client.stop()                # encerra threads + fecha session HTTP
        client.save(path)            # persiste antes de fechar
    """

    SERVER = "https://ntfy.sh"
    # ntfy mantém long-poll aberto ~30s; usamos 45s pra dar margem
    SUBSCRIBE_TIMEOUT = 45
    # Pausa entre tentativas de reconexão (backoff exponencial 2→4→8→16→30s).
    # Reseta pro inicial quando uma conexão dura > 5s ou recebe msg —
    # assim rede instável não escala indefinidamente.
    RECONNECT_BACKOFF_INITIAL_S = 2.0
    RECONNECT_BACKOFF_MAX_S = 30.0
    # Intervalo do monitor loop — 2s é um bom compromisso entre responsividade
    # e custo (image/pixel checks são moderadamente caros)
    MONITOR_INTERVAL_S = 2.0
    # Tag que marca mensagens publicadas pelo PC. Subscribe filtra essas pra
    # não tratar nossas próprias notificações como comandos (echo-back).
    # `desktop_computer` é uma tag conhecida do ntfy que vira o emoji 🖥️ no
    # app — funciona como marcador semântico (origem=PC) e visualmente fica
    # bonito ao invés de mostrar texto cru tipo "from-pc".
    PC_SOURCE_TAG = "desktop_computer"

    def __init__(self, driver) -> None:
        self._driver = driver
        self._topic_id: str = ""
        self._monitors: list[Monitor] = []
        # Comandos que o usuário autorizou serem aceitos do celular.
        # Vazio por padrão = nenhum comando funciona até user marcar.
        self._allowed_cmds: set[str] = set()
        self._running = False
        self._sub_thread: threading.Thread | None = None
        self._mon_thread: threading.Thread | None = None
        # Session HTTP do subscribe — guardada pra ser fechada no stop()
        # (interrompe o long-poll sem esperar timeout)
        self._sub_session = None
        # Callbacks pra UI (executados na thread do client; UI deve usar after())
        # on_command recebe (action, arg) — ex: ("run", "slot2"), ("status", "")
        self.on_command: Callable[[str, str], None] | None = None
        self.on_status_change: Callable[[str], None] | None = None
        # Debug: chamado pra TODA mensagem recebida (mesmo filtradas).
        # Recebe (raw_message, status) — status: "fired", "filtered:echo",
        # "filtered:not_allowed", "filtered:empty"
        self.on_activity: Callable[[str, str], None] | None = None
        # Notificação local (bandeja do Windows) — recebe (message, title).
        # Settado pela UI; pode ser None se PIL/pystray indisponíveis.
        self.on_pc_notify: Callable[[str, str], None] | None = None

    # ─────────────────────────────────────────────────────────────
    # Topic management
    # ─────────────────────────────────────────────────────────────
    def generate_topic(self) -> str:
        """Gera topic_id novo aleatório (~144 bits entropy, urlsafe)."""
        return secrets.token_urlsafe(18)

    def set_topic(self, topic_id: str) -> None:
        self._topic_id = topic_id

    @property
    def topic_id(self) -> str:
        return self._topic_id

    def has_topic(self) -> bool:
        return bool(self._topic_id)

    def topic_url(self) -> str:
        """URL HTTPS do tópico — usada pelo PC pra publish/subscribe."""
        return f"{self.SERVER}/autoclick-{self._topic_id}"

    @staticmethod
    def _sanitize_header(value: str) -> str:
        """Remove caracteres não-latin1 (emoji/CJK) que quebram HTTP headers.

        Bug raiz: `requests.put(headers={"Message": "📸 Screen"})` lança
        UnicodeEncodeError porque urllib3 codifica headers como latin-1.
        Sem isso, /screen (com emoji 📸 + anexo) falhava silenciosamente
        pois a exception era engolida no `except Exception` do publish().
        """
        if not value:
            return value
        try:
            value.encode("latin-1")
            return value  # já é latin-1, nada a fazer
        except UnicodeEncodeError:
            return value.encode("ascii", errors="ignore").decode("ascii").strip()

    def subscribe_deeplink(self) -> str:
        """Deeplink ntfy:// pro QR code.

        O app ntfy (Android/iOS) registra os schemes `ntfy://` e `ntfys://`
        como URL handlers. Escanear `ntfy://ntfy.sh/topic` abre direto o app
        e adiciona a subscription — não abre o site no navegador.

        Fallback: se o app não estiver instalado, o sistema mostra "abrir com…"
        em vez de abrir o site lento.
        """
        return f"ntfy://ntfy.sh/autoclick-{self._topic_id}"

    # ─────────────────────────────────────────────────────────────
    # Monitors / allowed commands (CRUD acessado pela UI)
    # ─────────────────────────────────────────────────────────────
    def get_monitors(self) -> list[Monitor]:
        return list(self._monitors)

    def set_monitors(self, monitors: list[Monitor]) -> None:
        self._monitors = list(monitors)

    def get_allowed_cmds(self) -> set[str]:
        return set(self._allowed_cmds)

    def set_allowed_cmds(self, cmds: set[str]) -> None:
        self._allowed_cmds = set(cmds)

    # ─────────────────────────────────────────────────────────────
    # Publish (qualquer thread pode chamar)
    # ─────────────────────────────────────────────────────────────
    def publish(self, message: str, title: str = "AutoClick Pro",
                 priority: int = 3, attach_screenshot: bool = False,
                 actions: list[dict] | None = None) -> bool:
        """POST mensagem no notify topic. Retorna True em sucesso.

        priority: 1=min, 3=default, 5=max (urgent)
        actions: lista de {"label": str, "body": str} — vira botão na notificação
                 que POSTa "body" no cmd topic (botão = comando remoto).
        attach_screenshot: captura tela completa e anexa como JPEG.
        """
        if not self._topic_id:
            return False
        try:
            import requests
        except ImportError:
            return False

        # HTTP headers só aceitam latin-1 — `requests` quebra com
        # UnicodeEncodeError se houver emoji/CJK. Sanitiza pra ASCII.
        headers = {
            "Title": self._sanitize_header(title),
            "Priority": str(priority),
            "Tags": self.PC_SOURCE_TAG,
        }
        if actions:
            # Formato ntfy: cada ação é "http, Label, URL, body=xxx, clear=true"
            # separadas por "; ". `clear=true` remove a notificação ao apertar.
            parts = []
            for a in actions:
                label = a.get("label", "Ação")
                body  = a.get("body", "")
                parts.append(
                    f"http, {label}, {self.topic_url()}, body={body}, clear=true"
                )
            headers["Actions"] = "; ".join(parts)

        try:
            if attach_screenshot:
                screenshot = self._capture_screenshot_jpeg()
                if screenshot is None:
                    return self._post_text(message, headers)
                headers["Filename"] = "screen.jpg"
                # Mensagem vai no header `Message` (não body) quando há anexo
                # → mesma sanitização anti-emoji que aplicamos no Title.
                headers["Message"]  = self._sanitize_header(message) or "(screenshot)"
                r = requests.put(self.topic_url(), data=screenshot,
                                  headers=headers, timeout=15)
                return r.ok
            else:
                return self._post_text(message, headers)
        except Exception:
            return False

    def _post_text(self, message: str, headers: dict) -> bool:
        import requests
        try:
            r = requests.post(self.topic_url(),
                               data=message.encode("utf-8"),
                               headers=headers, timeout=10)
            return r.ok
        except Exception:
            return False

    def _capture_screenshot_jpeg(self) -> bytes | None:
        """Captura tela inteira, redimensiona pra 1280×720 max, comprime JPEG q=70.

        Retorna bytes do JPEG ou None se PIL/ImageGrab não disponível.
        Tamanho típico: 150-300KB (ntfy aceita até 2MB).
        """
        try:
            from PIL import ImageGrab
            import io
            img = ImageGrab.grab()
            img.thumbnail((1280, 720))
            buf = io.BytesIO()
            # Converte pra RGB se for RGBA (JPEG não suporta alpha)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(buf, format="JPEG", quality=70)
            return buf.getvalue()
        except Exception:
            return None

    # ─────────────────────────────────────────────────────────────
    # Subscribe + Monitor loops
    # ─────────────────────────────────────────────────────────────
    def start(self) -> None:
        if self._running:
            return
        if not self._topic_id:
            return  # nada a fazer sem topic
        self._running = True
        self._sub_thread = threading.Thread(target=self._subscribe_loop,
                                              daemon=True)
        self._mon_thread = threading.Thread(target=self._monitor_loop,
                                              daemon=True)
        self._sub_thread.start()
        self._mon_thread.start()
        if self.on_status_change:
            try: self.on_status_change("connected")
            except Exception: pass

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        # Fecha a session HTTP pra interromper o long-poll imediatamente
        # (senão esperaria até SUBSCRIBE_TIMEOUT pra detectar self._running=False)
        if self._sub_session is not None:
            try: self._sub_session.close()
            except Exception: pass
            self._sub_session = None
        if self.on_status_change:
            try: self.on_status_change("disconnected")
            except Exception: pass

    @property
    def is_running(self) -> bool:
        return self._running

    def _subscribe_loop(self) -> None:
        """Long-poll no cmd topic via GET /topic/json (NDJSON stream).

        ntfy mantém a conexão aberta ~30s, depois fecha — reconectamos em loop.
        Backoff exponencial em falhas: 2→4→8→16→30s. Reseta pra 2s sempre que
        uma conexão dura >5s ou uma mensagem chega (sinal de "rede OK agora").
        """
        try:
            import requests
        except ImportError:
            return
        backoff = self.RECONNECT_BACKOFF_INITIAL_S
        while self._running:
            # monotonic: backoff reset baseado em tempo real decorrido, imune a NTP/DST
            connect_t = time.monotonic()
            try:
                self._sub_session = requests.Session()
                with self._sub_session.get(
                    f"{self.topic_url()}/json",
                    stream=True,
                    timeout=self.SUBSCRIBE_TIMEOUT,
                ) as r:
                    for line in r.iter_lines():
                        if not self._running:
                            break
                        if not line:
                            continue
                        # Recebeu algo → conexão saudável, reseta backoff
                        backoff = self.RECONNECT_BACKOFF_INITIAL_S
                        try:
                            event = json.loads(line)
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            continue
                        # ntfy envia "open" no início, depois "message" pra cada msg
                        if event.get("event") != "message":
                            continue
                        self._handle_message(event)
            except Exception:
                pass  # rede caiu, timeout, etc — reconecta
            # Conexão que sobreviveu > 5s = rede estava OK, reseta backoff
            if time.monotonic() - connect_t > 5.0:
                backoff = self.RECONNECT_BACKOFF_INITIAL_S
            if self._running:
                time.sleep(backoff)
                backoff = min(backoff * 2.0, self.RECONNECT_BACKOFF_MAX_S)

    def _handle_message(self, event: dict) -> None:
        """Processa uma mensagem do stream: filtra echo, parsa cmd+arg, dispara.

        Parsing de cmd:
          "/run slot2"  → action="run", arg="slot2"
          "/STOP"       → action="stop", arg=""
          "help"        → action="help", arg=""
        """
        raw_msg = (event.get("message") or "")
        # Ignora nossas próprias notificações (echo back)
        if self.PC_SOURCE_TAG in (event.get("tags") or []):
            if self.on_activity:
                try: self.on_activity(raw_msg, "filtered:echo")
                except Exception: pass
            return
        # Tira "/" ou "!" inicial, separa action de arg
        cleaned = raw_msg.strip().lstrip("/!").strip()
        if not cleaned:
            if self.on_activity:
                try: self.on_activity(raw_msg, "filtered:empty")
                except Exception: pass
            return
        parts = cleaned.split(maxsplit=1)
        action = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""
        if action not in self._allowed_cmds:
            if self.on_activity:
                try: self.on_activity(raw_msg, "filtered:not_allowed")
                except Exception: pass
            return
        if self.on_activity:
            try: self.on_activity(raw_msg, "fired")
            except Exception: pass
        if self.on_command:
            try: self.on_command(action, arg)
            except Exception: pass

    def _monitor_loop(self) -> None:
        """Avalia monitores image/pixel/text a cada N segundos."""
        while self._running:
            # monotonic: cooldown imune a mudanças do relógio do sistema
            now = time.monotonic()
            for mon in list(self._monitors):  # cópia: pode ser modificado pela UI
                if not mon.enabled:
                    continue
                if mon.trigger_type not in ("image", "pixel", "text"):
                    continue  # event/var são acionados externamente
                if now - mon._last_fired_t < mon.cooldown_s:
                    continue
                try:
                    if self._evaluate_monitor(mon):
                        mon._last_fired_t = now
                        self._fire_monitor(mon)
                except Exception:
                    pass  # avaliação individual quebrou — segue pros outros
            time.sleep(self.MONITOR_INTERVAL_S)

    def _get_monitor_region(self, mon: Monitor) -> tuple[int, int, int, int] | None:
        """Retorna (x, y, w, h) da janela alvo, ou None pra tela inteira.

        Se a janela alvo foi fechada (hwnd inválido), retorna None — degrada
        pra tela inteira em vez de quebrar o monitor silenciosamente.
        """
        if not mon.target_hwnd:
            return None
        try:
            return self._driver.get_window_rect(mon.target_hwnd)
        except Exception:
            return None

    def _evaluate_monitor(self, mon: Monitor) -> bool:
        """True se o trigger do monitor está ativo no momento."""
        region = self._get_monitor_region(mon)

        if mon.trigger_type == "image" and mon.image_data:
            return self._driver.find_image_on_screen(
                mon.image_data, mon.image_threshold, region=region,
            ) is not None
        if (mon.trigger_type == "pixel" and mon.color_rgb
                and mon.x is not None and mon.y is not None):
            # Pixel ignora region (coords são absolutas)
            try:
                r, g, b = self._driver.get_pixel_color(mon.x, mon.y)
            except Exception:
                return False
            tr, tg, tb = mon.color_rgb
            tol = mon.color_tolerance
            return (abs(r - tr) <= tol and abs(g - tg) <= tol
                    and abs(b - tb) <= tol)
        if mon.trigger_type == "text" and mon.text_to_find:
            return self._driver.find_text_on_screen(
                text=mon.text_to_find,
                region=region,
                match_mode=mon.text_match_mode,
                case_sensitive=mon.text_case_sensitive,
                lang=mon.text_lang or "eng",
                min_confidence=mon.text_min_confidence,
            ) is not None
        return False

    def _resolve_message(self, mon: Monitor, label: str = "") -> str:
        """Texto da notificação: prioriza custom_message; fallback nome/label."""
        if mon.custom_message.strip():
            return mon.custom_message.strip()
        if label:
            return f"{mon.name}: {label}" if mon.name else label
        return f"Disparou: {mon.name}" if mon.name else "Disparou"

    def _dispatch_notification(
        self, mon: Monitor, message: str, *,
        title: str = "AutoClick Pro — Alerta",
        priority: int = 4,
        actions: list[dict] | None = None,
    ) -> None:
        """Despacha pra PC (tray) e/ou celular (ntfy) conforme flags do monitor."""
        if mon.notify_pc and self.on_pc_notify:
            try:
                self.on_pc_notify(message, title)
            except Exception:
                pass
        if mon.notify_phone:
            self.publish(
                message=message, title=title, priority=priority,
                attach_screenshot=mon.attach_screenshot,
                actions=actions,
            )

    def _fire_monitor(self, mon: Monitor) -> None:
        """Dispara notificação do monitor (PC tray + celular conforme flags)."""
        actions = [
            {"label": "Parar Macro", "body": "stop"},
            {"label": "Pausar",      "body": "pause"},
        ]
        self._dispatch_notification(
            mon, self._resolve_message(mon),
            title="AutoClick Pro — Alerta", priority=4, actions=actions,
        )

    def fire_event(self, event_name: str, label: str = "") -> None:
        """Aciona monitores do tipo 'event' por nome.

        Chamado pela UI quando macro inicia/para/etc. Respeita cooldown.
        Silencioso se client não está rodando (evita spam ao iniciar/parar app).
        """
        if not self._running:
            return
        # monotonic: consistente com _monitor_loop (mesma base de tempo nos _last_fired_t)
        now = time.monotonic()
        for mon in list(self._monitors):
            if (mon.trigger_type != "event"
                    or mon.event_name != event_name
                    or not mon.enabled):
                continue
            if now - mon._last_fired_t < mon.cooldown_s:
                continue
            mon._last_fired_t = now
            self._dispatch_notification(
                mon, self._resolve_message(mon, label),
                title="AutoClick Pro — Alerta", priority=3,
            )

    # ─────────────────────────────────────────────────────────────
    # Persistência (atomic write como hotstrings/profiles)
    # ─────────────────────────────────────────────────────────────
    def load(self, path: str) -> None:
        """Restaura topic_id, allowed_cmds e monitores. Silencioso em erro."""
        if not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return
        try:
            self._topic_id = str(data.get("topic_id", "") or "")
            self._allowed_cmds = set(data.get("allowed_cmds", []) or [])
            known = Monitor.__dataclass_fields__
            self._monitors = []
            for m in data.get("monitors", []) or []:
                if not isinstance(m, dict):
                    continue
                # Filtra campos desconhecidos e campos runtime (_*)
                kwargs = {k: v for k, v in m.items()
                          if k in known and not k.startswith("_")}
                try:
                    self._monitors.append(Monitor(**kwargs))
                except (TypeError, ValueError):
                    pass
        except (TypeError, AttributeError):
            pass

    def save(self, path: str) -> None:
        """Atomic write — tmp + os.replace + fsync."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            "topic_id": self._topic_id,
            "allowed_cmds": sorted(self._allowed_cmds),
            "monitors": [
                {k: v for k, v in asdict(m).items() if not k.startswith("_")}
                for m in self._monitors
            ],
        }
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
