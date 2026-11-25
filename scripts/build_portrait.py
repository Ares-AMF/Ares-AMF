"""Convierte una foto en caricatura de colores planos y luego en ASCII monocromo.

Se corre una sola vez en local (necesita Pillow y numpy):

    pip install pillow numpy
    python scripts/build_portrait.py ruta/a/foto.jpg

Genera assets/avatar.png (caricatura) y assets/portrait.json (lo que usa generate.py).
Los recortes y el eje de simetría están calibrados para la foto actual; si cambias
de foto, ajusta CROP y AXIS.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ASSETS = Path(__file__).resolve().parent.parent / "assets"
CROP = (455, 420, 1175, 1400)   # cabeza y hombros en la foto original
WIDTH = 420                      # resolución de trabajo
SCALE = WIDTH / (CROP[2] - CROP[0])
AXIS = round((815 - CROP[0]) * SCALE)      # eje vertical de la cara (x=815 en la foto)
NECK_Y = round((1166 - CROP[1]) * SCALE)   # debajo de aquí ya no hay pared visible
HAIR_Y = round((1094 - CROP[1]) * SCALE)
COLS = 58                       # ancho del ASCII en caracteres

# nombre: (color de referencia en la foto, color plano de salida)
PALETTE = {
    "ink":    ((18, 12, 12),    (30, 24, 28)),
    "ink2":   ((45, 35, 34),    (58, 44, 46)),
    "skinS":  ((110, 70, 54),   (150, 92, 72)),
    "skinM":  ((160, 112, 92),  (204, 140, 110)),
    "skinL":  ((212, 160, 136), (240, 190, 160)),
    "shirtS": ((98, 86, 90),    (112, 108, 124)),
    "shirtL": ((154, 138, 141), (172, 170, 186)),
    "tieS":   ((140, 30, 42),   (160, 28, 44)),
    "tie":    ((210, 49, 67),   (229, 72, 77)),
    "glass":  ((137, 164, 133), (150, 214, 196)),
}
LINE_ART = (40, 26, 30)
# zona: (carácter, gris 0-255) — una "textura" distinta por zona para el ASCII monocromo
MONO = {
    "ink":    ("\"", 110),  # pelo
    "ink2":   ("~", 130),
    "skinL":  ("@", 240),
    "skinM":  ("*", 190),
    "skinS":  (";", 135),
    "shirtL": ("=", 205),
    "shirtS": ("-", 140),
    "tie":    ("#", 255),
    "tieS":   ("x", 170),
    "glass":  ("o", 255),
}


def grow(seed: np.ndarray, allowed: np.ndarray) -> np.ndarray:
    reg = seed & allowed
    while True:
        g = reg.copy()
        g[1:] |= reg[:-1]; g[:-1] |= reg[1:]; g[:, 1:] |= reg[:, :-1]; g[:, :-1] |= reg[:, 1:]
        g &= allowed
        if (g == reg).all():
            return reg
        reg = g


def person_mask(im: Image.Image) -> np.ndarray:
    a = np.asarray(im.filter(ImageFilter.MedianFilter(7))).astype(int)
    R, G = a[..., 0], a[..., 1]
    lum = a.mean(2)
    wall = (R - G <= 3) & (lum > 14) & (lum < 95) & (a.max(2) - a.min(2) < 14)
    seed = np.zeros_like(wall); seed[0] = True; seed[:, 0] = True; seed[:, -1] = True
    m = ~grow(seed, wall)
    m = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(9))) > 127
    # el lado derecho tiene sombra en la pared: se refleja la silueta izquierda
    out = m.copy()
    for x in range(AXIS, m.shape[1]):
        xm = 2 * AXIS - x
        out[:, x] = m[:, xm] if xm >= 0 else True
    out = np.asarray(Image.fromarray((out * 255).astype(np.uint8))
                     .filter(ImageFilter.GaussianBlur(1.5))) > 127
    # quitar restos de pared neutra alrededor de la cabeza
    raw = np.asarray(im.filter(ImageFilter.MedianFilter(5))).astype(int)
    neutral = ((raw[..., 0] - raw[..., 1] <= 4) & (raw.max(2) - raw.min(2) < 16)
               & (raw.mean(2) > 20) & (raw.mean(2) < 100))
    yy = np.arange(out.shape[0])[:, None]
    out &= ~(neutral & (yy < NECK_Y))
    return np.asarray(Image.fromarray((out * 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(7))) > 127


def main(src: str) -> None:
    im = Image.open(src).convert("RGB").crop(CROP)
    im = im.resize((WIDTH, int(WIDTH * im.height / im.width)), Image.LANCZOS)
    mask = person_mask(im)

    sm = im
    for _ in range(3):
        sm = sm.filter(ImageFilter.MedianFilter(7))
    a = np.asarray(sm).astype(float)
    names = list(PALETTE)
    ref = np.array([PALETTE[n][0] for n in names], float)
    lab = ((a[:, :, None, :] - ref[None, None]) ** 2).sum(3).argmin(2)
    L = Image.fromarray(lab.astype(np.uint8))
    for _ in range(2):
        L = L.filter(ImageFilter.ModeFilter(5))
    lab = np.asarray(L).astype(int).copy()
    lab[(lab == names.index("ink2")) & (np.arange(lab.shape[0])[:, None] < HAIR_Y)] = -1
    lab[~mask] = -1

    edges = np.asarray(im.convert("L").filter(ImageFilter.GaussianBlur(1.4))
                       .filter(ImageFilter.FIND_EDGES)).astype(int)
    lines = (edges > 9) & (lab >= 2)

    # caricatura
    flat = np.zeros(lab.shape + (3,), np.uint8); flat[:] = (18, 18, 22)
    for i, n in enumerate(names):
        flat[lab == i] = PALETTE[n][1]
    flat[lines] = LINE_ART
    Image.fromarray(flat).save(ASSETS / "avatar.png")
    toon = np.asarray(Image.fromarray(flat).convert("L")).astype(float)

    # ASCII monocromo: cada zona tiene su propio carácter y tono de gris,
    # y los contornos se dibujan con | - / \ según la dirección del borde
    g = np.asarray(im.convert("L").filter(ImageFilter.GaussianBlur(2))).astype(float)
    gy, gx = np.gradient(g)
    strong = lines
    h, w = lab.shape
    cw = w / COLS; ch = cw / 0.5625
    hexc = lambda v: "#%02x%02x%02x" % (v, v, v)
    rows = []
    for r in range(int(h / ch)):
        row: list[list] = []
        for c in range(COLS):
            y0, y1, x0, x1 = int(r * ch), int((r + 1) * ch), int(c * cw), int((c + 1) * cw)
            cell = lab[y0:y1, x0:x1].ravel(); fg = cell[cell >= 0]
            if len(fg) < len(cell) * .45:
                glyph, col = " ", None
            else:
                n = names[np.bincount(fg).argmax()]
                thr = .16 if n in ("skinL", "skinM", "glass") else .3  # rasgos finos de la cara
                if strong[y0:y1, x0:x1].mean() > thr and n not in ("ink", "ink2"):
                    sx, sy = gx[y0:y1, x0:x1].sum(), gy[y0:y1, x0:x1].sum()
                    ang = (np.degrees(np.arctan2(sy, sx)) + 90) % 180  # dirección de la línea
                    glyph = "-" if ang < 22.5 or ang >= 157.5 else "\\" if ang < 67.5 else "|" if ang < 112.5 else "/"
                    col = hexc(255)
                else:
                    glyph, v = MONO[n]
                    if n in ("ink", "ink2") and r * ch > HAIR_Y:  # traje: trama alterna
                        glyph = ":" if (r + c) % 2 else "."
                    col = hexc(v)
            if row and row[-1][1] == col:
                row[-1][0] += glyph
            else:
                row.append([glyph, col])
        rows.append(row)
    (ASSETS / "portrait.json").write_text(json.dumps({"cols": COLS, "rows": rows}, ensure_ascii=False),
                                          encoding="utf-8")
    print(f"ok: {len(rows)} filas x {COLS} columnas")


if __name__ == "__main__":
    main(sys.argv[1])
