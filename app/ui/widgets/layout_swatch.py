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

    # -- um desenho por layout (a anatomia real de cada um) -----------------------------------------------
    def _draw_classic(self, p, a):
        main = self._sidebar(p, a, 30)  # sidebar larga à esquerda
        main = self._topbar(p, main)  # barra de link e busca
        player = QRectF(main.left(), main.top(), main.width() - 31, main.height() * 0.52)
        self._player(p, player)
        self._lines(p, player.left(), player.bottom() + 5, 40, 2)
        self._tiles(p, player.left(), player.bottom() + 20, 18, 12, 3)
        details = QRectF(main.right() - 26, main.top(), 26, main.height())  # detalhes opcionais (tracejado)
        p.setPen(QPen(_color(self._tokens["border"]), 1, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(details, 3, 3)

    def _topnav(self, p, area, tabs=5):
        bar = QRectF(area.left(), area.top(), area.width(), 8)
        self._box(p, QRectF(bar.left() + 2, bar.top() + 1, 12, 5), "text_primary", 2)
        for i in range(tabs):
            self._box(p, QRectF(bar.left() + 20 + i * 14, bar.top() + 2.5, 10, 2.5), "accent" if i == 0 else "text_secondary", 1)
        self._box(p, QRectF(bar.right() - 30, bar.top() + 1, 18, 5), "surface_elevated", 2.5)
        self._box(p, QRectF(bar.right() - 10, bar.top() + 1, 10, 5), "accent", 2.5)
        return QRectF(area.left(), area.top() + 11, area.width(), area.height() - 11)

    def _draw_streaming(self, p, a):
        main = self._topnav(p, a)  # abas no topo, sem sidebar
        hero = QRectF(main.left(), main.top(), main.width(), main.height() * 0.46)  # destaque de ponta a ponta
        self._box(p, hero, "accent_soft", 0)
        self._box(p, QRectF(hero.left() + 5, hero.bottom() - 13, 30, 3), "text_primary", 1.5)
        self._box(p, QRectF(hero.left() + 5, hero.bottom() - 8, 14, 5), "accent", 2)
        for row in range(2):
            y = hero.bottom() + 5 + row * 17
            self._box(p, QRectF(main.left() + 4, y, 22, 2), "text_secondary", 1)
            self._tiles(p, main.left() + 4, y + 4, 22, 10, 4)

    def _draw_cinema(self, p, a):
        top = QRectF(a.left(), a.top(), a.width(), 9)  # cabeçalho translúcido
        grad = QLinearGradient(top.topLeft(), top.bottomLeft())
        grad.setColorAt(0, QColor(0, 0, 0, 200))
        grad.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(top, grad)
        for i in range(3):
            self._box(p, QRectF(a.left() + 4 + i * 14, a.top() + 3, 10, 2.5), "accent" if i == 0 else "text_secondary", 1)
        for row in range(2):  # mural de pôsteres
            for col in range(4):
                self._box(p, QRectF(a.left() + 2 + col * 29, a.top() + 14 + row * 26, 27, 24), "surface_elevated", 3)
        self._box(p, QRectF(a.left() + 2, a.top() + 14, 27, 24), "accent_soft", 3)
        self._box(p, QRectF(a.left() + 2, a.bottom() - 6, a.width() - 4, 2), "progress", 1)

    def _draw_manager(self, p, a):
        tree = QRectF(a.left(), a.top(), 26, a.height() - 8)  # árvore à esquerda
        self._box(p, tree, "surface", 3)
        for i in range(7):
            self._box(p, QRectF(tree.left() + 3 + (3 if i in (1, 2, 4, 5) else 0), tree.top() + 4 + i * 8, 14, 2.5),
                      "accent" if i == 1 else "text_secondary", 1)
        main = QRectF(tree.right() + 4, a.top(), a.width() - 30, a.height() - 8)
        ribbon = QRectF(main.left(), main.top(), main.width(), 8)  # faixa de ações
        self._box(p, ribbon, "surface_elevated", 2)
        for i in range(4):
            self._box(p, QRectF(ribbon.left() + 3 + i * 13, ribbon.top() + 2, 10, 4), "text_secondary", 1.5)
        table = QRectF(main.left(), ribbon.bottom() + 3, main.width() - 24, main.height() - 12)
        self._box(p, QRectF(table.left(), table.top(), table.width(), 5), "surface_hover", 2)
        for row in range(5):
            y = table.top() + 8 + row * 8
            if row == 1:
                self._box(p, QRectF(table.left(), y - 1, table.width(), 7), "accent_soft", 2)
            for col, w in enumerate((0.4, 0.14, 0.2, 0.16)):
                x = table.left() + 2 + sum((0.4, 0.14, 0.2, 0.16)[:col]) * table.width()
                self._box(p, QRectF(x, y + 1, table.width() * w - 4, 2.5), "text_secondary", 1)
        preview = QRectF(table.right() + 3, table.top(), 21, table.height())  # prévia
        self._box(p, preview, "surface", 3)
        self._box(p, QRectF(preview.left() + 2, preview.top() + 2, 17, 10), "accent_soft", 2)
        self._lines(p, preview.left() + 2, preview.top() + 16, 17, 3)
        self._box(p, QRectF(a.left(), a.bottom() - 6, a.width(), 6), "surface_elevated", 2)  # barra de estado

    def _draw_workstation(self, p, a):
        activity = QRectF(a.left(), a.top(), 8, a.height() - 8)  # barra de atividades
        self._box(p, activity, "surface_elevated", 2)
        for i in range(4):
            self._box(p, QRectF(activity.left() + 2, activity.top() + 4 + i * 9, 4, 4), "accent" if i == 0 else "text_secondary", 1.5)
        dock = QRectF(activity.right() + 3, a.top(), 30, a.height() - 8)  # painel com abas
        self._box(p, dock, "surface", 3)
        for i in range(3):
            self._box(p, QRectF(dock.left() + 2 + i * 9, dock.top() + 2, 7, 3), "accent" if i == 0 else "text_secondary", 1)
        for i in range(5):
            self._box(p, QRectF(dock.left() + 2, dock.top() + 9 + i * 9, dock.width() - 4, 7), "accent_soft" if i == 1 else "surface_elevated", 2)
        right = QRectF(a.right() - 30, a.top(), 30, a.height() - 8)
        center = QRectF(dock.right() + 3, a.top(), right.left() - dock.right() - 6, a.height() - 8)
        self._player(p, QRectF(center.left(), center.top(), center.width(), center.height() * 0.5))
        self._lines(p, center.left(), center.top() + center.height() * 0.5 + 4, center.width() * 0.7, 3)
        self._box(p, right, "surface", 3)
        self._lines(p, right.left() + 2, right.top() + 3, right.width() - 4, 2)
        self._box(p, QRectF(right.left() + 2, right.top() + 14, right.width() - 4, 22), "input_bg", 2)  # notas
        for i in range(3):  # marcadores
            self._box(p, QRectF(right.left() + 2, right.top() + 40 + i * 6, right.width() - 4, 4), "accent_soft", 1.5)
        self._box(p, QRectF(a.left(), a.bottom() - 6, a.width(), 6), "surface_elevated", 2)

    def _draw_compact(self, p, a):
        win = QRectF(a.center().x() - 26, a.top(), 52, a.height())  # janela pequena
        self._box(p, win, "surface", 4)
        head = QRectF(win.left(), win.top(), win.width(), 8)
        self._box(p, head, "surface_elevated", 4)
        self._box(p, QRectF(head.left() + 3, head.top() + 2.5, 5, 3), "text_secondary", 1)
        self._box(p, QRectF(head.right() - 17, head.top() + 2.5, 3, 3), "text_secondary", 1)
        p.setPen(Qt.NoPen)
        p.setBrush(_color(self._tokens["accent"]))
        p.drawEllipse(QPointF(head.right() - 8, head.top() + 4), 2, 2)  # alfinete: fica por cima
        self._player(p, QRectF(win.left() + 3, win.top() + 11, win.width() - 6, 28))
        for i in range(4):
            self._box(p, QRectF(win.left() + 3, win.top() + 43 + i * 8, win.width() - 6, 6), "accent_soft" if i == 0 else "surface_elevated", 2)
