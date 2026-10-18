from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame

from app.domain import states
from app.domain.states import format_duration
from app.styles.icons import icon
from app.ui.widgets.video_card import ActionsMixin, cover_pixmap

STREAMING, WALL = "streaming", "wall"
SIZES = {STREAMING: (300, 169, 54), WALL: (360, 203, 0)}  # largura, altura da imagem, altura do texto sob ela
HOVER_GROW = 6  # a imagem cresce isso (px) em cada lado ao passar o mouse


class PosterTile(ActionsMixin, QFrame):
    """Pôster de um vídeo, sem moldura de cartão. No modo 'streaming' o título fica sob a imagem; no 'wall' (mural do modo
    cinema) a imagem ocupa tudo e o título só aparece ao passar o mouse. O clique abre; botão direito abre o menu de ações."""

    open_requested = Signal(int)
    action_requested = Signal(int, str)
    selection_changed = Signal(int, bool)

    def __init__(self, translator, tokens, video, state, thumb_path=None, can_download=False, organize=None, watch="none",
                 fraction=0.0, can_forget=False, mode=STREAMING):
        super().__init__()
        self.video, self.state, self.watch = video, state, watch
        self._tr, self._tokens, self._mode = translator, tokens, mode
        self._can_download, self._organize, self._can_forget = can_download, organize, can_forget
        self._fraction = fraction
        self._hover = False
        self._selectable = False
        self._selected = False
        width, height, text = SIZES[mode]
        self._thumb_h, self._text_h = height, text
        self.setObjectName("posterTile")
        self.setFixedSize(width + 2 * HOVER_GROW, height + text + 2 * HOVER_GROW)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.setToolTip(video.title)
        state_text = translator.t(f"card.state_{state}") if state != states.SAVED else ""
        self.setAccessibleName(f"{video.title}. {state_text}".strip(". "))
        self._cover = cover_pixmap(thumb_path, width + 2 * HOVER_GROW, height + 2 * HOVER_GROW, 0, tokens)
        self._radius = tokens["radius"]["md"]

    def sizeHint(self):
        return self.size()

    # -- seleção (a biblioteca em lote usa a mesma interface dos cartões) ------------------------------
    def set_selectable(self, selectable):
        self._selectable = selectable
        if not selectable:
            self._selected = False
        self.update()

    @property
    def selected(self):
        return self._selected

    def set_selected(self, selected):
        if selected != self._selected:
            self._selected = selected
            self.selection_changed.emit(self.video.id, selected)
            self.update()

    # -- desenho --------------------------------------------------------------------------------------
    def _image_rect(self):
        grow = HOVER_GROW if self._hover or self.hasFocus() else 0
        inset = HOVER_GROW - grow
        return QRectF(inset, inset, self.width() - 2 * inset, self._thumb_h + 2 * grow)

    def paintEvent(self, _event):
        t = self._tokens
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        rect = self._image_rect()
        clip = QPainterPath()
        clip.addRoundedRect(rect, self._radius, self._radius)
        p.save()
        p.setClipPath(clip)
        p.drawPixmap(rect.toRect(), self._cover)
        wall = self._mode == WALL
        if wall:  # no mural, o texto vive sobre a imagem e só aparece com o mouse (ou o foco do teclado)
            veil = QLinearGradient(0, rect.top(), 0, rect.bottom())
            veil.setColorAt(0.45, QColor(0, 0, 0, 0))
            veil.setColorAt(1, QColor(0, 0, 0, 215 if (self._hover or self.hasFocus()) else 90))
            p.fillRect(rect, veil)
        if self._fraction > 0:
            bar = QRectF(rect.left(), rect.bottom() - 4, rect.width(), 4)
            p.fillRect(bar, QColor(0, 0, 0, 150))
            p.fillRect(QRectF(bar.left(), bar.top(), bar.width() * (1 if self.watch == "watched" else self._fraction), 4),
                       QColor(t["success"] if self.watch == "watched" else t["progress"]))
        p.restore()
        self._paint_badges(p, rect)
        if wall:
            if self._hover or self.hasFocus():
                self._paint_text(p, QRectF(rect.left() + 14, rect.bottom() - 62, rect.width() - 28, 50), QColor("#FFFFFF"), QColor("#E0E0E0"))
        else:
            self._paint_text(p, QRectF(HOVER_GROW, HOVER_GROW + self._thumb_h + 8, self.width() - 2 * HOVER_GROW, self._text_h),
                             QColor(t["text_primary"]), QColor(t["text_secondary"]))
        if self.hasFocus():
            p.setPen(QPen(QColor(t["focus"]), 3))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(rect.adjusted(1.5, 1.5, -1.5, -1.5), self._radius, self._radius)
        if self._selected:
            p.setPen(QPen(QColor(t["accent"]), 4))
            p.drawRoundedRect(rect.adjusted(2, 2, -2, -2), self._radius, self._radius)
        p.end()

    def _paint_badges(self, p, rect):
        duration = format_duration(self.video.duration)
        if duration:
            font = QFont(self.font())
            font.setPixelSize(12)
            font.setBold(True)
            p.setFont(font)
            fm = QFontMetrics(font)
            w = fm.horizontalAdvance(duration) + 12
            box = QRectF(rect.right() - w - 8, rect.bottom() - 24 - (4 if self._fraction > 0 else 0), w, 18)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 190))
            p.drawRoundedRect(box, 5, 5)
            p.setPen(QColor("#FFFFFF"))
            p.drawText(box, Qt.AlignCenter, duration)
        if self.state != states.SAVED:
            kind = {states.DOWNLOADED: ("check", self._tokens["downloaded_border"], self._tokens["text_on_downloaded"]),
                    states.FAILED: ("warning", self._tokens["error"], self._tokens["text_on_error"])}.get(
                self.state, ("warning", self._tokens["warning"], self._tokens["text_on_warning"]))
            circle = QRectF(rect.left() + 10, rect.top() + 10, 24, 24)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(kind[1]))
            p.drawEllipse(circle)
            pix = icon(kind[0], kind[2], 14).pixmap(14, 14)
            p.drawPixmap(int(circle.center().x() - 7), int(circle.center().y() - 7), pix)

    def _paint_text(self, p, area, title_color, meta_color):
        font = QFont(self.font())
        font.setPixelSize(14)
        font.setBold(True)
        fm = QFontMetrics(font)
        p.setFont(font)
        p.setPen(title_color)
        title = fm.elidedText(self.video.title or self.video.url, Qt.ElideRight, int(area.width()))
        p.drawText(QRectF(area.left(), area.top(), area.width(), fm.height()), Qt.AlignLeft | Qt.AlignVCenter, title)
        small = QFont(self.font())
        small.setPixelSize(12)
        p.setFont(small)
        p.setPen(meta_color)
        meta = " · ".join(x for x in (self.video.channel, format_duration(self.video.duration)) if x)
        p.drawText(QRectF(area.left(), area.top() + fm.height() + 2, area.width(), 18), Qt.AlignLeft | Qt.AlignVCenter,
                   QFontMetrics(small).elidedText(meta, Qt.ElideRight, int(area.width())))

    # -- interação -------------------------------------------------------------------------------------
    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def focusInEvent(self, event):
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.update()
        super().focusOutEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            if self._selectable:
                self.set_selected(not self._selected)
            else:
                self.open_requested.emit(self.video.id)
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        self._build_menu().exec(event.globalPos())

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            if self._selectable:
                self.set_selected(not self._selected)
            else:
                self.open_requested.emit(self.video.id)
            return
        if event.key() == Qt.Key_Menu:
            self._build_menu().exec(self.mapToGlobal(self.rect().center()))
            return
        super().keyPressEvent(event)
