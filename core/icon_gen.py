"""
core/icon_gen.py — Geração programática do ícone do AutoClick Pro.

Design: cursor branco + raio rosa sobre fundo escuro arredondado.
Usa supersampling 4x + LANCZOS para bordas suaves em todos os tamanhos.
"""
from __future__ import annotations

import os


def _draw_frame(sz: int) -> "Image":
    """Desenha o ícone num RGBA quadrado de lado `sz`."""
    from PIL import Image, ImageDraw

    SCALE = 4
    S = sz * SCALE

    img  = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── 1. Fundo quadrado arredondado ─────────────────────────────
    m = S * 0.04
    r = S * 0.22
    draw.rounded_rectangle([m, m, S - m, S - m],
                           radius=r, fill=(11, 13, 24, 255))

    # ── 2. Borda roxa ──────────────────────────────────────────────
    bw = max(2, S // 20)
    draw.rounded_rectangle([m, m, S - m, S - m],
                           radius=r, outline=(124, 115, 255, 255), width=bw)
    # Brilho interno
    draw.rounded_rectangle(
        [m + bw, m + bw, S - m - bw, S - m - bw],
        radius=max(1, r - bw),
        outline=(160, 150, 255, 60),
        width=max(1, bw // 2),
    )

    # ── 3. Cursor do mouse ─────────────────────────────────────────
    cs = S * 0.56   # tamanho do cursor
    cx = S * 0.13   # canto superior esquerdo
    cy = S * 0.11

    def _pts(dx: float = 0, dy: float = 0):
        return [
            (cx + dx,              cy + dy),
            (cx + dx,              cy + cs * 0.72 + dy),
            (cx + cs * 0.24 + dx,  cy + cs * 0.54 + dy),
            (cx + cs * 0.40 + dx,  cy + cs * 0.90 + dy),
            (cx + cs * 0.53 + dx,  cy + cs * 0.86 + dy),
            (cx + cs * 0.37 + dx,  cy + cs * 0.50 + dy),
            (cx + cs * 0.70 + dx,  cy + cs * 0.50 + dy),
        ]

    # Sombra do cursor
    draw.polygon(_pts(S * 0.025, S * 0.025), fill=(0, 0, 20, 160))
    # Cursor principal (branco levemente azulado)
    draw.polygon(_pts(), fill=(232, 232, 255, 255))
    # Highlight na borda esquerda (ponta mais brilhante)
    draw.polygon([
        (cx,              cy),
        (cx,              cy + cs * 0.55),
        (cx + cs * 0.07,  cy + cs * 0.46),
        (cx + cs * 0.07,  cy),
    ], fill=(255, 255, 255, 255))

    # ── 4. Raio elétrico (canto inferior direito) ──────────────────
    bs = S * 0.30
    bx = S * 0.57
    by = S * 0.56
    bolt = [
        (bx + bs * 0.52, by),
        (bx + bs * 0.06, by + bs * 0.50),
        (bx + bs * 0.42, by + bs * 0.50),
        (bx,             by + bs),
        (bx + bs * 0.94, by + bs * 0.52),
        (bx + bs * 0.58, by + bs * 0.52),
    ]
    # Sombra do raio
    draw.polygon([(x + S * 0.012, y + S * 0.012) for x, y in bolt],
                 fill=(80, 15, 30, 160))
    # Raio principal (rosa)
    draw.polygon(bolt, fill=(255, 107, 138, 255))
    # Highlight do raio
    draw.polygon([
        (bx + bs * 0.52, by),
        (bx + bs * 0.06, by + bs * 0.50),
        (bx + bs * 0.26, by + bs * 0.50),
        (bx + bs * 0.70, by),
    ], fill=(255, 175, 195, 200))

    # Downscale com anti-aliasing
    return img.resize((sz, sz), Image.LANCZOS)


def generate_icon_ico(path: str) -> bool:
    """Gera o ícone .ico com múltiplos tamanhos no `path` indicado.

    Retorna True em caso de sucesso, False se Pillow não estiver disponível.
    """
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        return False

    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        sizes = [16, 24, 32, 48, 64, 128, 256]
        frames = [_draw_frame(sz) for sz in sizes]
        frames[0].save(
            path,
            format="ICO",
            sizes=[(s, s) for s in sizes],
            append_images=frames[1:],
        )
        return True
    except Exception:
        return False
