"""Genera assets/logo.json: el isotipo de Chúuk en ASCII.

Solo librería estándar. La geometría viene de chuuk-isotipo-blanco.svg (viewBox 1400×1400):
  - una C: anillo de radio 400–700 centrado en (700, 700), abierto del lado derecho
    (de -45° a 90°, con y hacia abajo)
  - una cola recta: x 700–1400, y 1100–1400
  - un punto: círculo de radio 200 en (1200, 800)

    python scripts/build_logo.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
ROWS = 30            # alto del logo en caracteres
CELL_ASPECT = 0.56   # ancho / alto de un carácter monoespaciado
PAD_ROWS = 2         # aire arriba y abajo
RAMP = " .:-=+*#%@"
SS_X, SS_Y = 4, 7    # submuestreo por celda


def inside(x: float, y: float) -> bool:
    dx, dy = x - 700, y - 700
    r = math.hypot(dx, dy)
    if 400 <= r <= 700:
        ang = math.degrees(math.atan2(dy, dx))  # -180..180, y hacia abajo
        if not (-45 < ang < 90):
            return True
    if 700 <= x <= 1400 and 1100 <= y <= 1400:
        return True
    return math.hypot(x - 1200, y - 800) <= 200


def main() -> None:
    cell_h = 1400 / ROWS
    cell_w = cell_h * CELL_ASPECT
    cols = math.ceil(1400 / cell_w)
    x_off = (cols * cell_w - 1400) / 2
    lines = [" " * cols for _ in range(PAD_ROWS)]
    for r in range(ROWS):
        row = ""
        for c in range(cols):
            hits = 0
            for sy in range(SS_Y):
                for sx in range(SS_X):
                    x = c * cell_w - x_off + (sx + .5) * cell_w / SS_X
                    y = r * cell_h + (sy + .5) * cell_h / SS_Y
                    hits += inside(x, y)
            cov = hits / (SS_X * SS_Y)
            row += RAMP[min(len(RAMP) - 1, round(cov * (len(RAMP) - 1)))]
        lines.append(row)
    lines += [" " * cols for _ in range(PAD_ROWS)]
    (ASSETS / "logo.json").write_text(json.dumps({"cols": cols, "lines": lines}, ensure_ascii=False),
                                      encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
