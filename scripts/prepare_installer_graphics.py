"""Prepare l'image laterale NSIS (164x314 BMP) depuis assets/installateur.jpg."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC_CANDIDATES = (
    ROOT / "assets" / "installateur.jpg",
    ROOT / "installateur.jpg",
)
OUT_BMP = ROOT / "installer" / "wizard_sidebar.bmp"
TARGET_W = 164
TARGET_H = 314


def _crop_to_aspect(img: Image.Image, ratio: float, x_bias: float = 0.12) -> Image.Image:
    """Recadre en portrait ; x_bias decale le cadrage vers la gauche (arbre / train Starlink)."""
    w, h = img.size
    current = w / h
    if current > ratio:
        new_w = int(h * ratio)
        max_left = w - new_w
        left = int(max_left * x_bias)
        return img.crop((left, 0, left + new_w, h))
    new_h = int(w / ratio)
    max_top = h - new_h
    top = int(max_top * 0.35)
    return img.crop((0, top, w, top + new_h))


def main() -> int:
    src = next((p for p in SRC_CANDIDATES if p.is_file()), None)
    if src is None:
        print("Image introuvable : assets/installateur.jpg", file=sys.stderr)
        return 1

    img = Image.open(src).convert("RGB")
    cropped = _crop_to_aspect(img, TARGET_W / TARGET_H)
    sidebar = cropped.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)

    OUT_BMP.parent.mkdir(parents=True, exist_ok=True)
    sidebar.save(OUT_BMP, format="BMP")
    print(f"Bitmap installeur : {OUT_BMP} ({TARGET_W}x{TARGET_H})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
