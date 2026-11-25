"""Genera las tarjetas SVG estilo terminal del README de perfil.

Solo usa la librería estándar. Necesita la variable GITHUB_TOKEN
(en GitHub Actions ya existe; en local: `set GITHUB_TOKEN=$(gh auth token)`).

    python scripts/generate.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER", "Ares-AMF")
ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

# Paleta: guinda + dorado
BG = "#0d0d0f"
PANEL = "#141417"
BORDER = "#2a2a30"
TEXT = "#e8e6e3"
MUTED = "#8b8b94"
ACCENT = "#e0b04a"  # dorado
LEVELS = ["#1c1c21", "#4a1416", "#7a1a1c", "#b0262a", "#e5484d"]
MONO = "ui-monospace,SFMono-Regular,'Cascadia Code',Consolas,'Liberation Mono',monospace"
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


# ---------------------------------------------------------------- datos
def fetch_calendar() -> list[tuple[dt.date, int]]:
    query = """query($login:String!){user(login:$login){contributionsCollection{
      contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [(dt.date.fromisoformat(d["date"]), d["contributionCount"])
            for w in weeks for d in w["contributionDays"]]


def stats(days: list[tuple[dt.date, int]]) -> dict:
    counts = [c for _, c in days]
    total = sum(counts)
    active = sum(1 for c in counts if c)
    best_day, best = max(days, key=lambda x: x[1])

    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    # racha actual: hoy puede no tener commits todavía, así que se cuenta desde ayer
    current = 0
    seq = counts[:-1] if counts and counts[-1] == 0 else counts
    for c in reversed(seq):
        if not c:
            break
        current += 1

    monthly: dict[tuple[int, int], int] = {}
    for d, c in days:
        monthly[(d.year, d.month)] = monthly.get((d.year, d.month), 0) + c
    months = sorted(monthly.items())[-12:]
    return dict(total=total, active=active, best=best, best_day=best_day,
                longest=longest, current=current, span=len(days), avg=(total / active if active else 0),
                months=months)


# ---------------------------------------------------------------- svg helpers
def window(w: int, h: int, title: str, body: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{MONO}">
<style>
  .t{{fill:{TEXT}}} .m{{fill:{MUTED}}} .a{{fill:{ACCENT}}} .r{{fill:{LEVELS[4]}}}
  .cell{{opacity:0;animation:in .4s ease forwards}}
  .bar{{transform-box:fill-box;transform-origin:bottom;transform:scaleY(0);animation:grow .6s cubic-bezier(.2,.8,.2,1) forwards}}
  .cur{{animation:blink 1.1s steps(1) infinite}}
  .pr{{opacity:0;animation:pr .5s ease forwards}}
  .scan{{animation:scan 5s linear 1.6s infinite}}
  @keyframes pr{{0%{{opacity:0;filter:brightness(3)}}60%{{opacity:1}}100%{{opacity:1;filter:none}}}}
  @keyframes scan{{from{{transform:translateY(0)}}to{{transform:translateY(470px)}}}}
  @keyframes in{{to{{opacity:1}}}} @keyframes grow{{to{{transform:scaleY(1)}}}} @keyframes blink{{50%{{opacity:0}}}}
  @media (prefers-reduced-motion:reduce){{.cell,.bar,.pr{{animation:none;opacity:1;transform:none}} .cur,.scan{{animation:none}} .scan{{display:none}}}}
</style>
<rect width="{w}" height="{h}" rx="12" fill="{BG}" stroke="{BORDER}"/>
<circle cx="22" cy="20" r="5.5" fill="#ff5f57"/><circle cx="40" cy="20" r="5.5" fill="#febc2e"/><circle cx="58" cy="20" r="5.5" fill="#28c840"/>
<text x="{w/2}" y="24" text-anchor="middle" font-size="12" class="m">{escape(title)}</text>
<line x1="0" y1="40" x2="{w}" y2="40" stroke="{BORDER}"/>
{body}
</svg>"""


def prompt(x: int, y: int, cmd: str) -> str:
    return (f'<text x="{x}" y="{y}" font-size="14"><tspan class="r">ares</tspan>'
            f'<tspan class="m">@github</tspan><tspan class="t"> ~ $ </tspan>'
            f'<tspan class="a">{escape(cmd)}</tspan></text>')


def level(c: int, mx: int) -> str:
    if c == 0:
        return LEVELS[0]
    q = c / mx
    return LEVELS[1] if q <= .25 else LEVELS[2] if q <= .5 else LEVELS[3] if q <= .75 else LEVELS[4]


# ---------------------------------------------------------------- tarjeta 1: heatmap
def contributions_svg(days, s) -> str:
    W, cell, gap, x0, y0 = 880, 12, 3, 64, 112
    mx = max((c for _, c in days), default=1) or 1
    first = days[0][0]
    offset = (first.weekday() + 1) % 7  # GitHub empieza en domingo
    parts = [prompt(24, 72, "./contributions.sh")]
    last_month = None
    for i, (d, c) in enumerate(days):
        idx = i + offset
        col, row = idx // 7, idx % 7
        x, y = x0 + col * (cell + gap), y0 + row * (cell + gap)
        if row == 0 or i == 0:
            if d.month != last_month and (d.day <= 7 or (i == 0 and d.day <= 14)):
                parts.append(f'<text x="{x}" y="{y0-10}" font-size="11" class="m">{MESES[d.month-1]}</text>')
                last_month = d.month
        delay = col * 0.012
        parts.append(f'<rect class="cell" style="animation-delay:{delay:.2f}s" x="{x}" y="{y}" '
                     f'width="{cell}" height="{cell}" rx="2.5" fill="{level(c, mx)}">'
                     f'<title>{d.isoformat()}: {c}</title></rect>')
    for row, lab in ((1, "Lun"), (3, "Mié"), (5, "Vie")):
        parts.append(f'<text x="24" y="{y0 + row*(cell+gap) + 10}" font-size="11" class="m">{lab}</text>')
    yb = y0 + 7 * (cell + gap) + 30
    parts.append(f'<text x="{x0}" y="{yb}" font-size="13"><tspan class="t" font-weight="700">{s["total"]:,}</tspan>'
                 f'<tspan class="m"> contribuciones en el último año</tspan></text>')
    lx = W - 190
    parts.append(f'<text x="{lx}" y="{yb}" font-size="11" class="m">menos</text>')
    for k, col in enumerate(LEVELS):
        parts.append(f'<rect x="{lx+42+k*16}" y="{yb-10}" width="12" height="12" rx="2.5" fill="{col}"/>')
    parts.append(f'<text x="{lx+42+5*16+4}" y="{yb}" font-size="11" class="m">más</text>')
    return window(W, yb + 26, f"{USER.lower()}/README.md", "\n".join(parts))


# ---------------------------------------------------------------- tarjeta 2: whoami
def whoami_svg(s) -> str:
    W, H = 880, 470
    portrait = json.loads((ASSETS / "portrait.json").read_text(encoding="utf-8"))
    parts = [prompt(24, 72, "whoami")]
    # panel izquierdo: caricatura en ASCII a color (generada con scripts/build_portrait.py)
    px, py, pw, ph = 24, 92, 400, 350
    rows, ncols = portrait["rows"], portrait["cols"]
    tw_ = pw - 28
    lh = ph / (len(rows) + 1.2)
    fs = lh * 1.12
    parts.append(f'<defs><clipPath id="pc"><rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="8"/></clipPath>'
                 f'<linearGradient id="scan" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{LEVELS[4]}" stop-opacity="0"/>'
                 f'<stop offset=".5" stop-color="{LEVELS[4]}" stop-opacity=".16"/><stop offset="1" stop-color="{LEVELS[4]}" stop-opacity="0"/></linearGradient></defs>')
    parts.append(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="8" fill="{PANEL}" stroke="{BORDER}"/>')
    parts.append(f'<g clip-path="url(#pc)" font-size="{fs:.2f}" font-weight="700">')
    y_base = py + ph - lh * (len(rows) - 1) - 4
    for i, row in enumerate(rows):
        spans = "".join(f'<tspan fill="{col}">{escape(txt)}</tspan>' if col else escape(txt) for txt, col in row)
        parts.append(f'<text class="pr" style="animation-delay:{i*0.035:.3f}s" x="{px+14}" y="{y_base + i*lh:.1f}" '
                     f'textLength="{tw_}" lengthAdjust="spacing" xml:space="preserve">{spans}</text>')
    parts.append(f'<rect class="scan" x="{px}" y="{py-60}" width="{pw}" height="60" fill="url(#scan)"/>')
    parts.append('</g>')
    # panel derecho: métricas
    rx, rw = 440, W - 440 - 24
    tiles = [
        ("racha actual", f'{s["current"]}', "días"),
        ("racha más larga", f'{s["longest"]}', "días"),
        ("contribuciones", f'{s["total"]:,}', "último año"),
        ("días activos", f'{s["active"]}', 'último año'),
        ("mejor día", f'{s["best"]}', s["best_day"].strftime("%d/%m/%Y")),
        ("prom. / día activo", f'{s["avg"]:.1f}', "contribuciones"),
    ]
    tw, th = (rw - 12) / 2, 62
    for i, (lab, val, sub) in enumerate(tiles):
        x = rx + (i % 2) * (tw + 12)
        y = py + (i // 2) * (th + 10)
        parts.append(f'<rect x="{x}" y="{y}" width="{tw}" height="{th}" rx="8" fill="{PANEL}" stroke="{BORDER}"/>')
        parts.append(f'<text x="{x+14}" y="{y+20}" font-size="11" class="m">$ {lab}</text>')
        parts.append(f'<text x="{x+14}" y="{y+48}" font-size="24" font-weight="700" '
                     f'class="{"a" if i < 2 else "t"}">{val}</text>')
        parts.append(f'<text x="{x+tw-14}" y="{y+48}" font-size="11" text-anchor="end" class="m">{escape(sub)}</text>')
    # barras mensuales
    by = py + 3 * (th + 10)
    bh = py + ph - by
    parts.append(f'<rect x="{rx}" y="{by}" width="{rw}" height="{bh}" rx="8" fill="{PANEL}" stroke="{BORDER}"/>')
    parts.append(f'<text x="{rx+14}" y="{by+20}" font-size="11" class="m">$ contribuciones / mes</text>')
    months = s["months"]
    mx = max((v for _, v in months), default=1) or 1
    n = len(months)
    slot = (rw - 28) / n
    base = by + bh - 22
    top = by + 34
    for i, ((y, m), v) in enumerate(months):
        hgt = max(2, (base - top) * v / mx)
        x = rx + 14 + i * slot
        parts.append(f'<rect class="bar" style="animation-delay:{.3 + i*.05:.2f}s" x="{x+3:.1f}" y="{base-hgt:.1f}" '
                     f'width="{slot-6:.1f}" height="{hgt:.1f}" rx="2" fill="{level(v, mx) if v else LEVELS[0]}">'
                     f'<title>{MESES[m-1]} {y}: {v}</title></rect>')
        parts.append(f'<text x="{x+slot/2:.1f}" y="{base+14}" font-size="9" text-anchor="middle" class="m">{MESES[m-1][0]}</text>')
    parts.append(f'<text x="{W-24}" y="{H-12}" font-size="10" text-anchor="end" class="m">'
                 f'actualizado {dt.date.today().isoformat()}<tspan class="cur a"> ▍</tspan></text>')
    return window(W, H, f"{USER.lower()}/README.md", "\n".join(parts))


def main() -> None:
    days = fetch_calendar()
    s = stats(days)
    (ASSETS / "contributions.svg").write_text(contributions_svg(days, s), encoding="utf-8")
    (ASSETS / "whoami.svg").write_text(whoami_svg(s), encoding="utf-8")
    print(f"ok: {s['total']} contribuciones, racha actual {s['current']}, más larga {s['longest']}")


if __name__ == "__main__":
    main()
