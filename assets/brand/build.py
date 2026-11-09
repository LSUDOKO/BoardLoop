#!/usr/bin/env python3
"""Build the BoardLoop brand assets as SVG (text converted to outlines, so no font is needed to
view them), then PNGs with rsvg-convert.

    python assets/brand/build.py path/to/Outfit[wght].ttf

Outfit (SIL OFL 1.1) by Rodrigo Fuenzalida: https://github.com/Outfitio/Outfit-Fonts
"""
import subprocess
import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

OUT = Path(__file__).resolve().parent
GREEN, GREEN_HI, MINT = "#22d672", "#5cf29b", "#19c39a"
SILK = "#eef7f1"


def text_path(font: TTFont, text: str, size: float, x: float, y: float, tracking: float = 0) -> tuple[str, float]:
    """SVG path data for ``text`` with its baseline at (x, y); returns (d, advance width)."""
    gs, cmap, hmtx = font.getGlyphSet(), font.getBestCmap(), font["hmtx"]
    scale = size / font["head"].unitsPerEm
    pen = SVGPathPen(gs)
    cursor = 0.0
    for ch in text:
        name = cmap[ord(ch)]
        tp = TransformPen(pen, (scale, 0, 0, -scale, x + cursor, y))
        gs[name].draw(tp)
        cursor += hmtx[name][0] * scale + tracking
    return pen.getCommands(), cursor - tracking


def mark(x: float, y: float, s: float) -> str:
    """The BoardLoop mark: a stem and a cap built from pills (a 'b'), closing into a green loop."""
    k = s / 120
    return f"""<g transform="translate({x},{y}) scale({k})">
  <rect x="6" y="6" width="28" height="108" rx="14" fill="{SILK}"/>
  <rect x="46" y="6" width="58" height="28" rx="14" fill="{SILK}"/>
  <circle cx="74" cy="80" r="23" fill="none" stroke="url(#loop)" stroke-width="22"/>
</g>"""


DEFS = f"""<defs>
  <linearGradient id="loop" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{GREEN_HI}"/><stop offset="0.55" stop-color="{GREEN}"/><stop offset="1" stop-color="{MINT}"/>
  </linearGradient>
  <radialGradient id="glow" cx="50%" cy="50%" r="50%">
    <stop offset="0" stop-color="{GREEN}" stop-opacity="0.35"/><stop offset="1" stop-color="{GREEN}" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="bg" cx="38%" cy="45%" r="80%">
    <stop offset="0" stop-color="#0c4a28"/><stop offset="0.6" stop-color="#062b18"/><stop offset="1" stop-color="#021309"/>
  </radialGradient>
  <filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="3"/></filter>
  <filter id="lift" x="-10%" y="-10%" width="120%" height="140%"><feDropShadow dx="0" dy="6" stdDeviation="10" flood-color="#000" flood-opacity="0.45"/></filter>
</defs>"""


def wordmark(font: TTFont, x: float, y: float, size: float) -> tuple[str, float]:
    """'BoardLo' + green loop ring (the second o of Loop) + 'p'. Returns (svg, width)."""
    head, w1 = text_path(font, "BoardLo", size, x, y, tracking=-size * 0.02)
    ring_r = size * 0.255
    cx = x + w1 + size * 0.015 + ring_r + size * 0.03
    cy = y - size * 0.265
    ring = (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{ring_r:.1f}" fill="none" stroke="url(#loop)" '
            f'stroke-width="{size * 0.115:.1f}"/>')
    tail, w2 = text_path(font, "p", size, cx + ring_r + size * 0.06, y)
    width = (cx + ring_r + size * 0.06 + w2) - x
    return f'<path d="{head}" fill="{SILK}"/>{ring}<path d="{tail}" fill="{SILK}"/>', width


def traces(w: int, h: int, seed: int = 7) -> str:
    """PCB traces with pads, drawn deterministically so the art is reproducible."""
    import random

    rnd = random.Random(seed)
    out = []
    for i in range(18):
        side = i % 4
        y0 = rnd.randint(20, h - 20)
        x0 = rnd.randint(20, w - 20)
        step = rnd.choice([28, 36, 44])
        n = rnd.randint(2, 4)
        pts = []
        if side in (0, 1):  # from left/right edge, horizontal then 45° jog
            sx = -10 if side == 0 else w + 10
            d = 1 if side == 0 else -1
            pts = [(sx, y0)]
            x = sx
            for _ in range(n):
                x += d * rnd.randint(60, 180)
                pts.append((x, pts[-1][1]))
                jog = rnd.choice([-1, 1]) * step
                pts.append((x + d * abs(jog), pts[-1][1] + jog))
                x += d * abs(jog)
        else:  # from top/bottom edge
            sy = -10 if side == 2 else h + 10
            d = 1 if side == 2 else -1
            pts = [(x0, sy)]
            y = sy
            for _ in range(n):
                y += d * rnd.randint(50, 140)
                pts.append((pts[-1][0], y))
                jog = rnd.choice([-1, 1]) * step
                pts.append((pts[-1][0] + jog, y + d * abs(jog)))
                y += d * abs(jog)
        d_attr = "M" + " L".join(f"{px:.0f},{py:.0f}" for px, py in pts)
        bright = rnd.random() < 0.35
        color = GREEN if bright else "#1f7a46"
        op = 0.9 if bright else 0.45
        if bright:
            out.append(f'<path d="{d_attr}" fill="none" stroke="{GREEN}" stroke-width="7" stroke-opacity="0.35" '
                       f'filter="url(#soft)" stroke-linejoin="round"/>')
        out.append(f'<path d="{d_attr}" fill="none" stroke="{color}" stroke-opacity="{op}" stroke-width="2.4" '
                   f'stroke-linejoin="round" stroke-linecap="round"/>')
        ex, ey = pts[-1]
        out.append(f'<circle cx="{ex:.0f}" cy="{ey:.0f}" r="6" fill="#06200f" stroke="{color}" '
                   f'stroke-opacity="{op}" stroke-width="2.4"/>')
    return "\n".join(out)


def pill(x: float, y: float, w: float, label_path: str, icon: str) -> str:
    return (f'<rect x="{x}" y="{y}" width="{w}" height="58" rx="29" fill="#0b3a20" fill-opacity="0.55" '
            f'stroke="{GREEN}" stroke-width="2.5"/>{icon}<path d="{label_path}" fill="{SILK}"/>')


def chip_icon(x: float, y: float) -> str:
    pins = "".join(f'<rect x="{x + 7 + i * 7}" y="{y - 4}" width="2.5" height="5" fill="{SILK}"/>'
                   f'<rect x="{x + 7 + i * 7}" y="{y + 27}" width="2.5" height="5" fill="{SILK}"/>' for i in range(3))
    return (f'<rect x="{x + 3}" y="{y + 1}" width="26" height="26" rx="4" fill="none" stroke="{SILK}" stroke-width="2.4"/>'
            f'<rect x="{x + 10}" y="{y + 8}" width="12" height="12" rx="2" fill="none" stroke="{SILK}" stroke-width="2.2"/>{pins}')


def check_icon(x: float, y: float) -> str:
    return (f'<circle cx="{x + 15}" cy="{y + 14}" r="13" fill="none" stroke="{SILK}" stroke-width="2.4"/>'
            f'<path d="M{x + 9} {y + 14.5} l4.5 4.5 l8 -9" fill="none" stroke="{GREEN_HI}" stroke-width="3" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')


def hero(font: TTFont, w: int, h: int, size: float, pills: bool = True) -> str:
    mk = size * 1.1
    wm, ww = wordmark(font, 0, 0, size)
    total = mk + size * 0.32 + ww
    x0 = (w - total) / 2
    base = h * (0.47 if pills else 0.56)
    body = [f'<g filter="url(#lift)">{mark(x0, base - mk * 0.86, mk)}'
            f'<g transform="translate({x0 + mk + size * 0.32:.1f},{base:.1f})">{wm}</g></g>']
    if pills:
        lp1, w1 = text_path(font, "Compiles it", 26, 0, 0)
        lp2, w2 = text_path(font, "Proves it works", 26, 0, 0)
        pw1, pw2 = w1 + 96, w2 + 96
        gap = 26
        px = (w - (pw1 + gap + pw2)) / 2
        py = base + size * 0.42
        t1, _ = text_path(font, "Compiles it", 26, px + 70, py + 38)
        t2, _ = text_path(font, "Proves it works", 26, px + pw1 + gap + 70, py + 38)
        body.append(pill(px, py, pw1, t1, chip_icon(px + 24, py + 15)))
        body.append(pill(px + pw1 + gap, py, pw2, t2, check_icon(px + pw1 + gap + 24, py + 15)))
    return "\n".join(body)


def board_art(w: int, h: int) -> str:
    """A tilted ESP32-style module in the top-right corner, echoing the circuit-board look."""
    bw, bh = w * 0.30, h * 0.66
    x, y = w * 0.855, -h * 0.20
    pads = "".join(
        f'<rect x="{-5}" y="{40 + i * 24}" width="14" height="12" rx="6" fill="url(#gold)"/>'
        f'<rect x="{bw - 9:.0f}" y="{40 + i * 24}" width="14" height="12" rx="6" fill="url(#gold)"/>'
        for i in range(int((bh - 60) // 24)))
    smd = "".join(
        f'<rect x="{bw * 0.16 + (i % 4) * bw * 0.18:.0f}" y="{bh * 0.64 + (i // 4) * 30:.0f}" width="22" height="12" '
        f'rx="2" fill="#1d1f1e"/><rect x="{bw * 0.16 + (i % 4) * bw * 0.18 + 2:.0f}" y="{bh * 0.64 + (i // 4) * 30 + 2:.0f}" '
        f'width="5" height="8" fill="#b9a06a"/><rect x="{bw * 0.16 + (i % 4) * bw * 0.18 + 15:.0f}" '
        f'y="{bh * 0.64 + (i // 4) * 30 + 2:.0f}" width="5" height="8" fill="#b9a06a"/>' for i in range(8))
    sx, sy, sw, sh = bw * 0.14, bh * 0.10, bw * 0.72, bh * 0.44
    cx, cy = sx + sw / 2, sy + sh * 0.66
    wifi = "".join(f'<path d="M{cx - r:.0f} {cy:.0f} A{r} {r} 0 0 1 {cx + r:.0f} {cy:.0f}" fill="none" '
                   f'stroke="#8f9a95" stroke-width="7" stroke-linecap="round"/>' for r in (22, 42, 62))
    return f"""<defs>
  <linearGradient id="pcb" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#14703c"/><stop offset="1" stop-color="#0a4224"/></linearGradient>
  <linearGradient id="shield" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#d9e0dc"/><stop offset="0.5" stop-color="#aeb8b3"/><stop offset="1" stop-color="#8c9792"/></linearGradient>
  <linearGradient id="gold" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f0cf7a"/><stop offset="1" stop-color="#b8892f"/></linearGradient>
</defs>
<g transform="translate({x:.0f},{y:.0f}) rotate(26)" opacity="0.9" filter="url(#lift)">
  <rect width="{bw:.0f}" height="{bh:.0f}" rx="16" fill="url(#pcb)" stroke="{GREEN}" stroke-opacity="0.55" stroke-width="2.5"/>
  {pads}
  <rect x="{sx - 6:.0f}" y="{sy - 6:.0f}" width="{sw + 12:.0f}" height="{sh + 12:.0f}" rx="12" fill="#6d7873"/>
  <rect x="{sx:.0f}" y="{sy:.0f}" width="{sw:.0f}" height="{sh:.0f}" rx="9" fill="url(#shield)"/>
  {wifi}<circle cx="{cx:.0f}" cy="{cy:.0f}" r="7" fill="#8f9a95"/>
  {smd}
</g>"""


def canvas(font: TTFont, w: int, h: int, size: float, pills: bool = True, board: bool = True) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
{DEFS}
<rect width="{w}" height="{h}" fill="url(#bg)"/>
{traces(w, h)}
<ellipse cx="{w / 2}" cy="{h * 0.5}" rx="{w * 0.38}" ry="{h * 0.36}" fill="url(#glow)"/>
{board_art(w, h) if board else ""}
{hero(font, w, h, size, pills)}
</svg>"""


def main() -> None:
    font = instancer.instantiateVariableFont(TTFont(sys.argv[1]), {"wght": 600})
    files = {
        "banner.svg": canvas(font, 1200, 600, 118),            # catalog image (2:1)
        "social-preview.svg": canvas(font, 1280, 640, 124),    # GitHub social preview
        "og.svg": canvas(font, 1200, 630, 118),                # website Open Graph image
    }
    wm, ww = wordmark(font, 0, 0, 100)
    files["logo.svg"] = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -100 {110 + 32 + ww:.0f} 130">{DEFS}'
                         f'{mark(0, -96, 110)}<g transform="translate(142,0)">{wm}</g></svg>')
    files["mark.svg"] = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120">{DEFS}'
                         f'<rect width="120" height="120" rx="28" fill="#06301a"/>{mark(14, 14, 92)}</svg>')
    for name, svg in files.items():
        (OUT / name).write_text(svg, encoding="utf-8")
    renders = [("banner.svg", "../banner.png", 1200), ("social-preview.svg", "social-preview.png", 1280),
               ("og.svg", "og.png", 1200), ("mark.svg", "mark-512.png", 512), ("logo.svg", "logo-1200.png", 1200)]
    for src, dst, width in renders:
        subprocess.run(["rsvg-convert", "-w", str(width), str(OUT / src), "-o", str(OUT / dst)], check=True)
    print("built", ", ".join(files))


if __name__ == "__main__":
    main()
