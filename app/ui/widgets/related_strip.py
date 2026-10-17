from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from app.domain.states import format_duration
from app.ui.widgets.thumb_row import ThumbRow, title_label
from app.ui.widgets.video_card import cover_pixmap

ITEM_W, ITEM_H = 190, 107


class RelatedItem(QFrame):
    """Miniatura compacta de um vídeo parecido: clique ou Enter abre."""

    open_requested = Signal(int)

    def __init__(self, tokens, video, thumbnail_path):
        super().__init__()
        self.video_id = video.id
        self.setObjectName("relatedItem")
        self.setFixedWidth(ITEM_W)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        duration = format_duration(video.duration)
        self.setAccessibleName(f"{video.title}. {video.channel}. {duration}".strip())
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)
        thumb = QLabel()
        thumb.setPixmap(cover_pixmap(thumbnail_path, ITEM_W, ITEM_H, 10, tokens))
        thumb.setFixedSize(ITEM_W, ITEM_H)
        column.addWidget(thumb)
        title = QLabel(video.title)
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        title.setMaximumHeight(38)
        meta = QLabel(" · ".join(x for x in (video.channel, duration) if x))
        meta.setObjectName("cardMeta")
        column.addWidget(title)
        column.addWidget(meta)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.open_requested.emit(self.video_id)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.open_requested.emit(self.video_id)
            return
        super().keyPressEvent(event)


class RelatedStrip(QFrame):
    """"Mais da sua biblioteca": vídeos parecidos com o que está aberto, em uma fileira horizontal. Some quando não há nenhum."""

    video_opened = Signal(int)

    def __init__(self, translator, tokens):
        super().__init__()
        self.setObjectName("relatedStrip")
        self._tr = translator
        self._tokens = tokens
        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._row = None
        self._allowed = True
        self.items = []
        self.hide()

    def set_allowed(self, allowed):
        """O layout decide se a fileira aparece (ex.: o modo cinema não mostra)."""
        self._allowed = allowed
        self.setVisible(allowed and bool(self.items))

    def set_tokens(self, tokens):
        self._tokens = tokens

    def set_videos(self, videos, thumbnail_for):
        if self._row is not None:
            self._column.removeWidget(self._row)
            self._row.setParent(None)
            self._row.deleteLater()
            self._row = None
        self.items = [RelatedItem(self._tokens, v, thumbnail_for(v)) for v in videos]
        for item in self.items:
            item.open_requested.connect(self.video_opened)
        if not self.items:
            self.hide()
            return
        self._row = ThumbRow(
            self._tokens, title_label(self._tr.t("related.title")), self.items, None,
            self._tr.t("stream.prev"), self._tr.t("stream.next"),
        )
        self._column.addWidget(self._row)
        self.setVisible(self._allowed)
