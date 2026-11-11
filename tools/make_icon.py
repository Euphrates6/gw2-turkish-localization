"""Generates the minimalist IDE-themed hexagon app icon (assets/app_icon.ico + png).

Mirrors the Phosphor `ph-hexagon` logo used in the Hub sidebar: a light-grey hexagon
outline on a dark #181818 rounded square.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SS = 4  # supersampling factor
SIZE = 256


def hexagon(cx: float, cy: float, r: float) -> list[tuple[float, float]]:
    # Pointy-top hexagon, same orientation as Phosphor's ph-hexagon
    return [(cx + r * math.cos(math.radians(60 * i - 90)), cy + r * math.sin(math.radians(60 * i - 90))) for i in range(6)]


def render(size: int) -> Image.Image:
    s = size * SS
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pad = int(s * 0.03)
    d.rounded_rectangle([pad, pad, s - pad, s - pad], radius=int(s * 0.18),
                        fill=(24, 24, 24, 255), outline=(51, 51, 51, 255), width=max(SS, int(s * 0.015)))
    cx = cy = s / 2
    r = s * 0.33
    w = max(SS * 2, int(s * 0.065))
    pts = hexagon(cx, cy, r)
    d.polygon(pts, fill=(30, 30, 30, 255))
    d.line(pts + [pts[0], pts[1]], fill=(204, 204, 204, 255), width=w, joint="curve")
    return im.resize((size, size), Image.LANCZOS)


def main() -> None:
    big = render(1024)
    for out in (ROOT / "assets" / "app_icon.png", ROOT / "hub" / "ui" / "app_icon.png"):
        big.save(out, format="PNG")
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [render(sz) for sz in sizes]
    for out in (ROOT / "assets" / "app_icon.ico", ROOT / "hub" / "ui" / "favicon.ico"):
        frames[-1].save(out, format="ICO", sizes=[(sz, sz) for sz in sizes], append_images=frames[:-1])
    print("Hexagon icon generated.")


if __name__ == "__main__":
    main()

