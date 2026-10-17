from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton

from app.domain import layouts
from app.ui.widgets.theme_swatch import _color

SWATCH_SIZE = (170, 128)


class LayoutSwatch(QAbstractButton):
    """Miniatura (wireframe) de um layout, desenhada com as cores do tema atual: a prévia mostra a combinação real."""

    def __init__(self, key, label, tokens):
        super().__init__()
        self.layout_key = key
        self._text = label
        self._tokens = tokens
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(*SWATCH_SIZE)
        self.setFocusPolicy(Qt.StrongFocus)
        self.set_label(label)

    def set_label(self, label, description=""):
        self._text = label
        self.setAccessibleName(label)
        self.setToolTip(f"{label}\n{description}" if description else label)
        self.update()

    def set_tokens(self, tokens):
        self._tokens = tokens
        self.update()

    # ------------------------------------------------------------------------------------
    def paintEvent(self, _event):
        t = self._tokens
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        outer = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        preview = QRectF(outer.left(), outer.top(), outer.width(), outer.height() - 28)
        clip = QPainterPath()
        clip.addRoundedRect(preview, 10, 10)
        p.save()
        p.setClipPath(clip)
        grad = QLinearGradient(preview.topLeft(), preview.bottomRight())
        grad.setColorAt(0, _color(t["bg_start"]))
        grad.setColorAt(1, _color(t["bg_end"]))
        p.fillRect(preview, grad)
        getattr(self, f"_draw_{self.layout_key}")(p, preview.adjusted(5, 5, -5, -5))
        p.restore()

        ring = _color(t["accent_fg"])
        p.setPen(QPen(ring if self.isChecked() else QColor(128, 134, 150, 90), 2 if self.isChecked() else 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(preview, 10, 10)

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
            p.setBrush(ring)
            p.drawEllipse(QPointF(cx, cy), 9, 9)
            tick = QPen(QColor("#000000") if ring.lightness() > 140 else QColor("#FFFFFF"), 2)
            tick.setCapStyle(Qt.RoundCap)
            tick.setJoinStyle(Qt.RoundJoin)
            p.setPen(tick)
            p.drawPolyline([QPointF(cx - 4, cy), QPointF(cx - 1, cy + 3), QPointF(cx + 4, cy - 3)])
        if self.hasFocus():
            p.setPen(QPen(_color(self._tokens["focus"]), 2, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 12, 12)
        p.end()

    # -- helpers de desenho ---------------------------------------------------------------
    def _box(self, p, rect, key, radius=3):
        p.setPen(Qt.NoPen)
        p.setBrush(_color(self._tokens[key]))
        p.drawRoundedRect(rect, radius, radius)

    def _lines(self, p, x, y, width, count, gap=7, key="text_secondary", height=3):
        for i in range(count):
            self._box(p, QRectF(x, y + i * gap, width * (1 if i % 2 == 0 else 0.7), height), key, 1.5)

    def _sidebar(self, p, area, width, icons=False):
        side = QRectF(area.left(), area.top(), width, area.height())
        self._box(p, side, "surface", 3)
        self._box(p, QRectF(side.left() + 3, side.top() + 5, side.width() - 6, 5), "accent")
        for i in range(4):
            self._box(p, QRectF(side.left() + 3, side.top() + 15 + i * 8, side.width() - (6 if icons else 12), 3), "text_secondary", 1.5)
        return QRectF(side.right() + 4, area.top(), area.width() - width - 4, area.height())

    def _topbar(self, p, area, height=7):
        self._box(p, QRectF(area.left(), area.top(), area.width(), height), "surface_elevated", 3)
        return QRectF(area.left(), area.top() + height + 4, area.width(), area.height() - height - 4)

    def _tiles(self, p, x, y, w, h, count, gap=4):
        for i in range(count):
            self._box(p, QRectF(x + i * (w + gap), y, w, h), "surface_elevated", 2)
            self._box(p, QRectF(x + i * (w + gap), y + h - 1, w, 1), "border", 0)

    def _player(self, p, rect, progress=True):
        self._box(p, rect, "surface", 3)
        self._box(p, QRectF(rect.center().x() - 3, rect.center().y() - 3, 6, 6), "text_secondary", 3)
        if progress:
            bar = QRectF(rect.left() + 3, rect.bottom() - 5, rect.width() - 6, 2)
            self._box(p, bar, "border", 1)
            self._box(p, QRectF(bar.left(), bar.top(), bar.width() * 0.45, 2), "progress", 1)

    # -- um desenho por layout -------------------------------------------------------------
    def _draw_classic(self, p, a):
        main = self._sidebar(p, a, 30)
        main = self._topbar(p, main)
        details = QRectF(main.right() - 26, main.top(), 26, main.height())
        player = QRectF(main.left(), main.top(), main.width() - 31, main.height() * 0.52)
        self._player(p, player)
        self._lines(p, player.left(), player.bottom() + 5, 40, 2)
        self._tiles(p, player.left(), player.bottom() + 20, 18, 12, 3)
        p.setPen(QPen(_color(self._tokens["border"]), 1, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(details, 3, 3)
        self._lines(p, details.left() + 3, details.top() + 5, 20, 3, key="border")

    def _draw_streaming(self, p, a):
        main = self._sidebar(p, a, 14, icons=True)
        main = self._topbar(p, main)
        hero = QRectF(main.left(), main.top(), main.width(), main.height() * 0.42)
        self._box(p, hero, "accent_soft", 4)
        self._box(p, QRectF(hero.left() + 5, hero.bottom() - 13, 30, 3), "text_primary", 1.5)
        self._box(p, QRectF(hero.left() + 5, hero.bottom() - 8, 14, 5), "accent", 2)
        for row in range(2):
            y = hero.bottom() + 6 + row * 20
            self._box(p, QRectF(main.left(), y, 24, 2), "text_secondary", 1)
            self._tiles(p, main.left(), y + 5, 22, 11, 4)

    def _draw_cinema(self, p, a):
        self._box(p, a, "surface", 4)
        self._box(p, QRectF(a.center().x() - 5, a.center().y() - 5, 10, 10), "text_secondary", 5)
        self._box(p, QRectF(a.left() + 4, a.top() + 4, a.width() * 0.4, 4), "surface_elevated", 2)  # título que some
        bar = QRectF(a.left() + 6, a.bottom() - 8, a.width() - 12, 3)
        self._box(p, bar, "border", 1.5)
        self._box(p, QRectF(bar.left(), bar.top(), bar.width() * 0.4, 3), "progress", 1.5)

    def _draw_manager(self, p, a):
        main = self._sidebar(p, a, 14, icons=True)
        main = self._topbar(p, main)
        for i in range(4):  # filtros avançados
            self._box(p, QRectF(main.left() + i * 20, main.top(), 17, 6), "accent_soft" if i == 0 else "surface_elevated", 3)
        head = QRectF(main.left(), main.top() + 10, main.width(), 6)
        self._box(p, head, "surface_hover", 2)
        for row in range(5):
            y = head.bottom() + 3 + row * 8
            if row == 1:
                self._box(p, QRectF(main.left(), y - 1, main.width(), 7), "accent_soft", 2)
            for col, w in enumerate((0.38, 0.12, 0.16, 0.14, 0.12)):
                x = main.left() + 2 + sum((0.38, 0.12, 0.16, 0.14, 0.12)[:col]) * main.width()
                self._box(p, QRectF(x, y + 1, main.width() * w - 4, 2.5), "text_secondary", 1)

    def _draw_workstation(self, p, a):
        main = self._sidebar(p, a, 14, icons=True)
        left_w = main.width() * 0.26
        right_w = main.width() * 0.28
        left = QRectF(main.left(), main.top(), left_w, main.height())
        right = QRectF(main.right() - right_w, main.top(), right_w, main.height())
        center = QRectF(left.right() + 4, main.top(), main.width() - left_w - right_w - 8, main.height())
        self._box(p, left, "surface", 3)
        for i in range(5):
            self._box(p, QRectF(left.left() + 3, left.top() + 4 + i * 11, left.width() - 6, 8), "accent_soft" if i == 1 else "surface_elevated", 2)
        self._player(p, QRectF(center.left(), center.top(), center.width(), center.height() * 0.55))
        self._lines(p, center.left(), center.top() + center.height() * 0.55 + 5, center.width() * 0.6, 3)
        self._box(p, right, "surface", 3)
        self._lines(p, right.left() + 3, right.top() + 5, right.width() - 6, 2)
        self._box(p, QRectF(right.left() + 3, right.top() + 20, right.width() - 6, right.height() - 36), "input_bg", 2)  # notas
        for i in range(2):
            self._box(p, QRectF(right.left() + 3 + i * 14, right.bottom() - 11, 12, 6), "accent_soft", 3)

    def _draw_compact(self, p, a):
        win = QRectF(a.center().x() - 24, a.top(), 48, a.height())
        self._box(p, win, "surface", 4)
        self._box(p, QRectF(win.left() + 3, win.top() + 3, win.width() - 6, 3), "surface_elevated", 1.5)
        self._player(p, QRectF(win.left() + 3, win.top() + 9, win.width() - 6, 30))
        for i in range(4):
            self._box(p, QRectF(win.left() + 3, win.top() + 43 + i * 9, win.width() - 6, 7), "accent_soft" if i == 0 else "surface_elevated", 2)
        p.setPen(Qt.NoPen)
        p.setBrush(_color(self._tokens["accent"]))
        p.drawEllipse(QPointF(win.right() - 6, win.top() + 4.5), 2, 2)  # alfinete: ficar por cima
