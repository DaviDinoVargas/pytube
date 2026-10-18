from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from app.domain.states import format_duration
from app.ui.widgets.video_card import cover_pixmap

THUMB_W, THUMB_H = 150, 84
PANEL_WIDTH = 380


class UpNextRow(QFrame):
    open_requested = Signal(int)

    def __init__(self, tokens, video, thumbnail_path, current=False):
        super().__init__()
        self.video_id = video.id
        self.setObjectName("upNextRow")
        self.setProperty("current", current)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        duration = format_duration(video.duration)
        self.setAccessibleName(f"{video.title}. {video.channel}. {duration}".strip())
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 6, 8, 6)
        row.setSpacing(12)
        thumb = QLabel()
        thumb.setPixmap(cover_pixmap(thumbnail_path, THUMB_W, THUMB_H, 8, tokens))
        thumb.setFixedSize(THUMB_W, THUMB_H)
        text = QVBoxLayout()
        text.setSpacing(2)
        title = QLabel(video.title)
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        title.setMaximumHeight(title.fontMetrics().lineSpacing() * 3 + 2)
        meta = QLabel(" · ".join(x for x in (video.channel, duration) if x))
        meta.setObjectName("cardMeta")
        text.addWidget(title)
        text.addWidget(meta)
        text.addStretch(1)
        row.addWidget(thumb)
        row.addLayout(text, 1)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.open_requested.emit(self.video_id)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.open_requested.emit(self.video_id)
            return
        super().keyPressEvent(event)


class UpNextPanel(QFrame):
    """Coluna 'A seguir' do layout Streaming: a fila (se houver) e depois vídeos parecidos, em linhas com miniatura."""

    video_opened = Signal(int)

    def __init__(self, translator, tokens):
        super().__init__()
        self.setObjectName("upNext")
        self.setFixedWidth(PANEL_WIDTH)
        self._tr = translator
        self._tokens = tokens
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("upNextScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("upNextContent")
        self._column = QVBoxLayout(content)
        self._column.setContentsMargins(4, 0, 4, 12)
        self._column.setSpacing(2)
        self.scroll.setWidget(content)
        outer.addWidget(self.scroll)
        self.rows = []
        self.headings = []
        self.empty_label = QLabel()
        self.empty_label.setObjectName("cardMeta")
        self.empty_label.setWordWrap(True)

    def set_tokens(self, tokens):
        self._tokens = tokens

    def set_items(self, queue_videos, related_videos, thumbnail_for, current_id=None):
        while self._column.count():
            item = self._column.takeAt(0)
            widget = item.widget()
            if widget is self.empty_label:
                widget.hide()  # reaproveitado; os demais itens são recriados
            elif widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.rows, self.headings = [], []
        t = self._tr.t
        for key, videos in (("upnext.queue", queue_videos), ("upnext.related", related_videos)):
            if not videos:
                continue
            heading = QLabel(t(key).upper())
            heading.setObjectName("groupTitle")
            self._column.addWidget(heading)
            self.headings.append(heading)
            for video in videos:
                row = UpNextRow(self._tokens, video, thumbnail_for(video), current=video.id == current_id)
                row.open_requested.connect(self.video_opened)
                self._column.addWidget(row)
                self.rows.append(row)
        if not self.rows:
            self.empty_label.setText(t("upnext.empty"))
            self._column.addWidget(self.empty_label)
            self.empty_label.show()
        self._column.addStretch(1)

    def retranslate(self):
        self.empty_label.setText(self._tr.t("upnext.empty"))
