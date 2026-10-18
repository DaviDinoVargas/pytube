"""Fundo da janela de cada tema: gradiente base mais um padrão (manchas de luz, grade, linhas de varredura, papel…).
Os painéis translúcidos do tema aparecem sobre ele, e é isso que dá a sensação de vidro, papel ou tela antiga."""

from PySide6.QtCore import QPointF, QRandomGenerator, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QWidget

from app.styles.colors import qcolor, with_alpha

NONE, ORBS, AURORA, SUN, VIGNETTE, GRID, DOTS, SCANLINES, PAPER, BLOBS, BRUSHED, FROST = (
    "none", "orbs", "aurora", "sun", "vignette", "grid", "dots", "scanlines", "paper", "blobs", "brushed", "frost",
)
KINDS = (NONE, ORBS, AURORA, SUN, VIGNETTE, GRID, DOTS, SCANLINES, PAPER, BLOBS, BRUSHED, FROST)

_noise_cache = {}


def _noise_tile(light):
    """Ruído fino, sempre o mesmo, que lembra papel (claro) ou grão (escuro)."""
    if light not in _noise_cache:
        image = QImage(128, 128, QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        rng = QRandomGenerator(12345)
        for y in range(128):
            for x in range(128):
                if rng.bounded(100) < 38:
                    shade = rng.bounded(60)
                    image.setPixelColor(x, y, QColor(0, 0, 0, 5 + shade // 6) if light else QColor(255, 255, 255, 3 + shade // 10))
        _noise_cache[light] = QPixmap.fromImage(image)
    return _noise_cache[light]


def _glow(p, rect, cx, cy, radius, color, alpha=170):
    """Mancha de luz macia: gradiente radial que termina em transparente."""
    center = QPointF(rect.left() + rect.width() * cx, rect.top() + rect.height() * cy)
    r = max(rect.width(), rect.height()) * radius
    gradient = QRadialGradient(center, r)
    gradient.setColorAt(0, with_alpha(color, alpha))
    gradient.setColorAt(0.55, with_alpha(color, alpha // 3))
    gradient.setColorAt(1, with_alpha(color, 0))
    p.fillRect(rect, QBrush(gradient))


def paint_backdrop(p, rect, t):
    rect = QRectF(rect)
    base = QLinearGradient(rect.topLeft(), rect.bottomRight())
    base.setColorAt(0, qcolor(t["bg_start"]))
    base.setColorAt(1, qcolor(t["bg_end"]))
    p.fillRect(rect, base)
    kind = t.get("backdrop", NONE)
    colors = t.get("backdrop_colors") or (t["accent"], t["accent_hover"])
    light = t["scheme"] == "light"
    if kind == ORBS:  # vidro: manchas de cor grandes e macias por trás dos painéis
        for (cx, cy, radius), color in zip(((0.12, 0.18, 0.55), (0.88, 0.12, 0.5), (0.72, 0.88, 0.62), (0.08, 0.92, 0.42)),
                                           (colors * 2)[:4]):
            _glow(p, rect, cx, cy, radius, color, 190)
    elif kind == AURORA:
        _glow(p, rect, 0.1, 0.1, 0.7, colors[0], 120)
        _glow(p, rect, 0.95, 0.9, 0.6, colors[-1], 110)
    elif kind == SUN:
        _glow(p, rect, 0.5, 1.05, 0.75, colors[0], 150)
        _glow(p, rect, 0.5, 1.15, 0.4, colors[-1], 110)
    elif kind == BLOBS:  # pastel: bolhas suaves de várias cores
        for (cx, cy, radius), color in zip(((0.1, 0.15, 0.4), (0.9, 0.2, 0.34), (0.75, 0.9, 0.45), (0.2, 0.85, 0.3), (0.5, 0.4, 0.2)),
                                           (colors * 3)[:5]):
            _glow(p, rect, cx, cy, radius, color, 95)
    elif kind == VIGNETTE:
        gradient = QRadialGradient(rect.center(), max(rect.width(), rect.height()) * 0.75)
        gradient.setColorAt(0.55, QColor(0, 0, 0, 0))
        gradient.setColorAt(1, QColor(0, 0, 0, 150))
        p.fillRect(rect, QBrush(gradient))
    elif kind in (GRID, DOTS):
        step = 28 if kind == GRID else 20
        line = with_alpha(colors[0], 34 if kind == GRID else 60)
        if kind == GRID:
            p.setPen(QPen(line, 1))
            x = rect.left()
            while x < rect.right():
                p.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
                x += step
            y = rect.top()
            while y < rect.bottom():
                p.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
                y += step
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(line)
            y = rect.top() + step / 2
            while y < rect.bottom():
                x = rect.left() + step / 2
                while x < rect.right():
                    p.drawRect(QRectF(x, y, 2, 2))
                    x += step
                y += step
        if len(colors) > 1:
            _glow(p, rect, 0.9, 0.05, 0.5, colors[-1], 55)
    elif kind == SCANLINES:
        _glow(p, rect, 0.5, 0.45, 0.7, colors[0], 38)
        p.setPen(QPen(QColor(0, 0, 0, 70), 1))
        y = rect.top()
        while y < rect.bottom():
            p.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            y += 3
    elif kind == PAPER:
        p.drawTiledPixmap(rect.toRect(), _noise_tile(light))
    elif kind == FROST:  # vidro líquido: brilho de luz que atravessa o vidro, grão fosco e uma borda de luz no topo
        sheen = QLinearGradient(rect.topLeft(), rect.bottomRight())
        sheen.setColorAt(0, QColor(255, 255, 255, 46))
        sheen.setColorAt(0.35, QColor(255, 255, 255, 6))
        sheen.setColorAt(0.65, QColor(255, 255, 255, 0))
        sheen.setColorAt(1, QColor(255, 255, 255, 22))
        p.fillRect(rect, QBrush(sheen))
        p.drawTiledPixmap(rect.toRect(), _noise_tile(False))
        edge = QLinearGradient(rect.topLeft(), rect.topRight())
        edge.setColorAt(0, QColor(255, 255, 255, 0))
        edge.setColorAt(0.5, QColor(255, 255, 255, 120))
        edge.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(QRectF(rect.left(), rect.top(), rect.width(), 1.5), QBrush(edge))
    elif kind == BRUSHED:  # metal escovado: fios horizontais finos
        rng = QRandomGenerator(777)
        for y in range(int(rect.top()), int(rect.bottom()), 2):
            alpha = 6 + rng.bounded(14)
            p.setPen(QPen(QColor(255, 255, 255, alpha) if rng.bounded(2) else QColor(0, 0, 0, alpha), 1))
            p.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))


class BackdropWidget(QWidget):
    """Raiz da janela: desenha o fundo do tema atrás de tudo."""

    def __init__(self, tokens):
        super().__init__()
        self._tokens = tokens
        self.setObjectName("root")
        self.setAttribute(Qt.WA_StyledBackground, False)

    def set_tokens(self, tokens):
        self._tokens = tokens
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        paint_backdrop(p, self.rect(), self._tokens)
        p.end()
