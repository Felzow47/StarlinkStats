"""Genere assets/starlink_widget.ico depuis assets/Vector.svg."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
SVG_CANDIDATES = (
    ROOT / "assets" / "Vector.svg",
    ROOT / "Vector.svg",
)
ICO = ROOT / "assets" / "starlink_widget.ico"
SIZES = (16, 24, 32, 48, 64, 128, 256)
MASTER_SIZE = 1024


def _find_svg() -> Path | None:
    for path in SVG_CANDIDATES:
        if path.is_file():
            return path
    return None


def _render_master(renderer: QSvgRenderer) -> Image.Image:
    pix = QPixmap(MASTER_SIZE, MASTER_SIZE)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()

    qimg = pix.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    w, h = qimg.width(), qimg.height()
    ptr = qimg.bits()
    ptr.setsize(qimg.sizeInBytes())
    return Image.frombytes("RGBA", (w, h), bytes(ptr))


def _build_sizes(master: Image.Image) -> list[Image.Image]:
    return [
        master.resize((size, size), Image.Resampling.LANCZOS)
        for size in SIZES
    ]


def _save_ico(images: list[Image.Image], path: Path) -> None:
    ordered = sorted(images, key=lambda img: img.width, reverse=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered[0].save(
        path,
        format="ICO",
        sizes=[(img.width, img.height) for img in ordered],
        append_images=ordered[1:],
    )


def main() -> int:
    svg = _find_svg()
    if svg is None:
        print("SVG introuvable : assets/Vector.svg", file=sys.stderr)
        return 1

    app = QApplication([])
    renderer = QSvgRenderer(str(svg))
    if not renderer.isValid():
        print(f"SVG invalide : {svg}", file=sys.stderr)
        return 1

    master = _render_master(renderer)
    images = _build_sizes(master)
    _save_ico(images, ICO)
    print(f"Icone ecrite : {ICO} ({len(images)} tailles) depuis {svg.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
