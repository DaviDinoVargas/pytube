from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# Quadrado arredondado roxo com um triângulo de "play" e uma linha de progresso.
_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">'
    '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#8B7CFF"/><stop offset="1" stop-color="#5B47E0"/></linearGradient></defs>'
    '<rect width="256" height="256" rx="56" fill="url(#g)"/>'
    '<path d="M96 72l96 56-96 56z" fill="#FFFFFF"/>'
    '<path d="M72 200h112" stroke="#FFFFFF" stroke-opacity=".6" stroke-width="12" stroke-linecap="round"/>'
    "</svg>"
)
SIZES = (16, 24, 32, 48, 64, 128, 256)


def render(size):
    renderer = QSvgRenderer(QByteArray(_SVG.encode()))
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return image


def app_icon():
    icon = QIcon()
    for size in SIZES:
        icon.addPixmap(QPixmap.fromImage(render(size)))
    return icon
