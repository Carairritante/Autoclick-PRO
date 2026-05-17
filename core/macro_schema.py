"""
core/macro_schema.py — Dataclasses e serialização de perfis.

Formatos suportados:
  v1 (legado): único dict flat com todos os campos mesclados
  v2 (atual):  dict com sub-chaves "script" e "ui" separadas

Retrocompatibilidade: script_from_dict e ui_from_dict aceitam ambos os formatos.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class MacroStep:
    """Representa um passo de ação em um macro sequencial.

    action: 'click' | 'double_click' | 'right_click' | 'move'
            'type' | 'wait' | 'scroll' | 'key_press' | 'pixel_check' | 'image_click'
    delay_ms: espera ANTES de executar o step (exceto em 'wait', onde É o tempo de espera)
    rel_x/rel_y: coordenadas relativas à janela-alvo (0.0–1.0); None = usar x/y absolutos
    color_rgb: [R,G,B] alvo para pixel_check; None = sem verificação
    image_data: PNG do template em base64 para image_click; None = sem template
    """
    action: str
    x: int | None = None
    y: int | None = None
    delay_ms: int = 0
    button: str = "left"
    text: str | None = None
    key: str | None = None
    scroll_dy: int = 3
    repeat: int = 1
    rel_x: float | None = None
    rel_y: float | None = None
    color_rgb: list | None = None
    skip_steps: int = 0
    color_condition: str = "match"
    color_tolerance: int = 10
    image_data: str | None = None
    image_threshold: float = 0.9
    image_timeout_ms: int = 5000
    image_skip_steps: int = 0
    # OCR — usa x,y como canto superior esquerdo da região
    ocr_w: int = 0
    ocr_h: int = 0
    ocr_var: str = ""
    ocr_lang: str = "eng"
    ocr_whitelist: str = ""
    ocr_to_number: bool = False
    # Variáveis — set_var, increment (via add com value=1)
    var_name: str = ""
    var_value: str = ""
    var_op: str = "set"
    # Condicionais — if step (else/endif não usam campos extras, só marcam blocos)
    cond_type: str = "var"     # "var" | "image" | "pixel"
    cond_op: str = "=="        # var: ==,!=,<,>,<=,>=,contains,starts_with
                                # image: "present" | "absent"
                                # pixel: "match" | "no_match"
    cond_value: str = ""
    # Drag — usa x,y como origem; x2,y2 como destino; rel_x2,rel_y2 análogos a rel_x/rel_y
    x2: int | None = None
    y2: int | None = None
    rel_x2: float | None = None
    rel_y2: float | None = None
    drag_duration_ms: int = 300
    # wait_image — reusa image_data/threshold/timeout; controla o que esperar
    image_wait_for: str = "present"   # "present" | "absent"
    # call_macro — referencia outro macro por slot (1/2/3) OU caminho de arquivo
    call_target_kind: str = "slot"   # "slot" | "file"
    call_target: str = "1"            # número do slot (string) ou caminho absoluto


@dataclass
class StopCondition:
    """Condição checada entre cada step de um macro; se disparar, para a execução.

    Diferente de MacroStep: não é executável, é uma observação contínua.
    """
    type: str = "image"            # "image" | "pixel" | "var"
    # image
    image_data: str | None = None
    image_threshold: float = 0.9
    # pixel
    x: int | None = None
    y: int | None = None
    color_rgb: list | None = None
    color_tolerance: int = 10
    # var
    var_name: str = ""
    var_op: str = "=="
    var_value: str = ""
    # comportamento
    enabled: bool = True
    label: str = ""                 # nome amigável: "Game Over detectado"


@dataclass
class MacroScript:
    """Configuração completa de automação (sem preferências de UI)."""
    version: int = 2
    mouse_button: str = "left"
    click_type: str = "single"
    burst: str = "1"
    interval_h: str = "0"
    interval_m: str = "0"
    interval_s: str = "0"
    interval_ms: str = "100"
    pos_mode: str = "cursor"
    pos_x: str = "500"
    pos_y: str = "400"
    seq_positions: list = field(default_factory=list)
    rep_mode: str = "infinite"
    rep_count: str = "100"
    humanize: bool = False
    humanize_pct: str = "10"
    jitter: bool = False
    jitter_px: str = "5"
    overlay: bool = False
    type_text: str = ""
    type_interval: str = "50"
    type_rep_mode: str = "infinite"
    type_rep_count: str = "10"
    type_delay: str = "3"
    type_paste: bool = False
    type_enter: bool = False
    type_interval_max: str = ""
    macro_speed: str = "1"
    macro_steps: list = field(default_factory=list)  # list of MacroStep dicts
    stop_conditions: list = field(default_factory=list)  # list of StopCondition dicts
    macro_notify_done: bool = False   # mostra notificação tray ao terminar


@dataclass
class UIProfile:
    """Preferências de UI do usuário (hotkeys, som). Sem lógica de automação."""
    version: int = 2
    hk_clk: str = "f6"
    hk_key: str = "f7"
    hk_macro: str = "f9"
    hk_stop: str = "f8"
    hk_rec: str = "f10"
    hk_pause: str = "pause"
    sound: bool = False


# ── Serialização ──────────────────────────────────────────────────────────────

def macrostep_to_dict(step: MacroStep) -> dict[str, Any]:
    return asdict(step)


def macrostep_from_dict(d: dict[str, Any]) -> MacroStep:
    """Reconstrói MacroStep a partir de dict; campos ausentes usam defaults."""
    known = MacroStep.__dataclass_fields__
    return MacroStep(**{k: v for k, v in d.items() if k in known})


def stop_cond_to_dict(sc: StopCondition) -> dict[str, Any]:
    return asdict(sc)


def stop_cond_from_dict(d: dict[str, Any]) -> StopCondition:
    """Reconstrói StopCondition a partir de dict; campos ausentes usam defaults."""
    known = StopCondition.__dataclass_fields__
    return StopCondition(**{k: v for k, v in d.items() if k in known})


def script_to_dict(s: MacroScript) -> dict[str, Any]:
    return asdict(s)


def ui_to_dict(u: UIProfile) -> dict[str, Any]:
    return asdict(u)


def script_from_dict(d: dict[str, Any]) -> MacroScript:
    """Constrói MacroScript a partir de dict v1 (flat) ou v2 (com sub-chave 'script').

    Campos ausentes usam os defaults do dataclass.
    """
    # v2: perfil contém sub-dict 'script'
    source = d.get("script", d)
    known = MacroScript.__dataclass_fields__
    kwargs: dict[str, Any] = {k: v for k, v in source.items() if k in known}
    kwargs["version"] = 2
    return MacroScript(**kwargs)


def ui_from_dict(d: dict[str, Any]) -> UIProfile:
    """Constrói UIProfile a partir de dict v1 (flat) ou v2 (com sub-chave 'ui').

    Campos ausentes usam os defaults do dataclass.
    """
    # v2: perfil contém sub-dict 'ui'
    source = d.get("ui", d)
    known = UIProfile.__dataclass_fields__
    kwargs: dict[str, Any] = {k: v for k, v in source.items() if k in known}
    kwargs["version"] = 2
    return UIProfile(**kwargs)


def profile_to_dict(script: MacroScript, ui: UIProfile) -> dict[str, Any]:
    """Serializa script + UI em único dict v2 (para salvar em arquivo ou slot)."""
    return {
        "version": 2,
        "script": script_to_dict(script),
        "ui": ui_to_dict(ui),
    }
