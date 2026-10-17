from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton

from app.styles.tokens import THEMES

SWATCH_SIZE = (150, 112)


def _color(value):
    """Converte '#RRGGBB' ou 'rgba(r, g, b, a)' em QColor."""
    value = value.strip()
    if value.startswith("rgba"):
        r, g, b, a = [int(float(p)) for p in value[value.index("(") + 1 : value.index(")")].split(",")]
        return QColor(r, g, b, a)
    return QColor(value)


class ThemeSwatch(QAbstractButton):
    """Cartão com a miniatura de um tema. O próprio desenho usa os tokens do tema que representa."""

    def __init__(self, name, label, ring_color):
        super().__init__()
        self.theme_name = name
        self._ring = _color(ring_color)
        self._text = label
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(*SWATCH_SIZE)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(label)
        self.setToolTip(label)

    def set_label(self, label):
        self._text = label
        self.setAccessibleName(label)
        self.setToolTip(label)
        self.update()

    def set_ring_color(self, color):
        self._ring = _color(color)
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        outer = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        preview = QRectF(outer.left(), outer.top(), outer.width(), outer.height() - 28)

        clip = QPainterPath()
        clip.addRoundedRect(preview, 12, 12)
        p.save()
        p.setClipPath(clip)
        if self.theme_name == "system":
            self._paint_theme(p, preview, THEMES["dark"])
            half = QPainterPath()
            half.moveTo(preview.right(), preview.top())
            half.lineTo(preview.right(), preview.bottom())
            half.lineTo(preview.left(), preview.bottom())
            half.closeSubpath()
            p.setClipPath(half.intersected(clip))
            self._paint_theme(p, preview, THEMES["light"])
        else:
            self._paint_theme(p, preview, THEMES[self.theme_name])
        p.restore()

        border = QPen(self._ring if self.isChecked() else QColor(128, 134, 150, 90), 2 if self.isChecked() else 1)
        p.setPen(border)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(preview, 12, 12)

        font = QFont(self.font())
        font.setPixelSize(12)
        font.setBold(self.isChecked())
        p.setFont(font)
        p.setPen(self.palette().windowText().color())
        text_rect = QRectF(outer.left(), preview.bottom() + 4, outer.width() - 22, 22)
        p.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.fontMetrics().elidedText(self._text, Qt.ElideRight, int(text_rect.width())))

        if self.isChecked():  # marca de seleção: não depende só de cor
            cx, cy = outer.right() - 9, preview.bottom() + 15
            p.setPen(Qt.NoPen)
            p.setBrush(self._ring)
            p.drawEllipse(QPointF(cx, cy), 9, 9)
            tick = QPen(QColor("#000000") if self._ring.lightness() > 140 else QColor("#FFFFFF"), 2)
            tick.setCapStyle(Qt.RoundCap)
            tick.setJoinStyle(Qt.RoundJoin)
            p.setPen(tick)
            p.drawPolyline([QPointF(cx - 4, cy), QPointF(cx - 1, cy + 3), QPointF(cx + 4, cy - 3)])

        if self.hasFocus():
            p.setPen(QPen(self._ring, 2, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 14, 14)
        p.end()

    @staticmethod
    def _paint_theme(p, rect, t):
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0, _color(t["bg_start"]))
        grad.setColorAt(1, _color(t["bg_end"]))
        p.fillRect(rect, grad)
        side = QRectF(rect.left(), rect.top(), rect.width() * 0.28, rect.height())
        p.fillRect(side, _color(t["surface"]))
        # itens da sidebar
        p.setPen(Qt.NoPen)
        p.setBrush(_color(t["accent"]))
        p.drawRoundedRect(QRectF(side.left() + 6, rect.top() + 14, side.width() - 12, 7), 3.5, 3.5)
        p.setBrush(_color(t["text_secondary"]))
        for i in range(2):
            p.drawRoundedRect(QRectF(side.left() + 6, rect.top() + 28 + i * 12, side.width() - 18, 5), 2.5, 2.5)
        # barra superior e "player"
        top = QRectF(side.right() + 8, rect.top() + 8, rect.width() - side.width() - 16, 10)
        p.setBrush(_color(t["surface_elevated"]))
        p.drawRoundedRect(top, 5, 5)
        player = QRectF(side.right() + 8, top.bottom() + 8, rect.width() - side.width() - 16, rect.height() - 52)
        p.setBrush(_color(t["surface"]))
        p.drawRoundedRect(player, t["radius"]["sm"] * 0.6, t["radius"]["sm"] * 0.6)
        bar = QRectF(player.left(), player.bottom() + 6, player.width(), 4)
        p.setBrush(_color(t["border"]).lighter(140))
        p.drawRoundedRect(bar, 2, 2)
        p.setBrush(_color(t["accent"]))
        p.drawRoundedRect(QRectF(bar.left(), bar.top(), bar.width() * 0.45, 4), 2, 2)
