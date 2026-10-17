from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from app.domain import states
from app.domain.query import LibraryQuery, SORT_NEWEST
from app.domain.states import format_duration, video_state
from app.ui.widgets.video_card import cover_pixmap

THUMB_W, THUMB_H = 84, 47
LIST_LIMIT = 300  # linhas desenhadas; a busca refina o resto
PANE_WIDTH = 270


class _Row(QWidget):
    def __init__(self, tokens, video, thumbnail_path, state):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(4, 4, 4, 4)
        row.setSpacing(10)
        thumb = QLabel()
        thumb.setPixmap(cover_pixmap(thumbnail_path, THUMB_W, THUMB_H, 6, tokens))
        thumb.setFixedSize(THUMB_W, THUMB_H)
        text = QVBoxLayout()
        text.setSpacing(2)
        title = QLabel(video.title)
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        title.setMaximumHeight(36)
        bits = [format_duration(video.duration)]
        if state == states.DOWNLOADED:
            bits.append("✓")
        elif state in (states.MISSING, states.INVALID, states.FAILED):
            bits.append("⚠")
        meta = QLabel(" · ".join(b for b in bits if b))
        meta.setObjectName("cardMeta")
        text.addWidget(title)
        text.addWidget(meta)
        text.addStretch(1)
        row.addWidget(thumb)
        row.addLayout(text, 1)
        for child in self.findChildren(QLabel):
            child.setAttribute(Qt.WA_TransparentForMouseEvents)


class LibraryList(QFrame):
    """Lista compacta da biblioteca com busca, para o painel esquerdo do layout Estação de trabalho."""

    video_opened = Signal(int)

    def __init__(self, translator, tokens, library, org):
        super().__init__()
        self.setObjectName("libraryList")
        self.setMinimumWidth(PANE_WIDTH - 60)
        self._tr = translator
        self._tokens = tokens
        self._library = library
        self._org = org
        self._current = None
        self._dirty = True
        column = QVBoxLayout(self)
        column.setContentsMargins(8, 10, 8, 8)
        column.setSpacing(8)
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self._timer.start())
        column.addWidget(self.search)
        self.list = QListWidget()
        self.list.setObjectName("libraryListView")
        self.list.setFrameShape(QFrame.NoFrame)
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setSpacing(2)
        self.list.itemActivated.connect(self._activated)
        self.list.itemClicked.connect(self._activated)
        column.addWidget(self.list, 1)
        self.count_label = QLabel()
        self.count_label.setObjectName("cardMeta")
        column.addWidget(self.count_label)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self.refresh)
        library.changed.connect(self.mark_dirty)
        self.retranslate()

    def mark_dirty(self):
        self._dirty = True
        if self.isVisible():
            self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        if self._dirty:
            self.refresh()

    def set_tokens(self, tokens):
        self._tokens = tokens
        self.mark_dirty()

    def set_current(self, video_id):
        self._current = video_id
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.data(Qt.UserRole) == video_id:
                self.list.setCurrentItem(item)
                self.list.scrollToItem(item)
                return
        self.list.clearSelection()

    def refresh(self):
        self._dirty = False
        videos = self._org.query(LibraryQuery(text=self.search.text(), sort=SORT_NEWEST))
        self.list.blockSignals(True)
        self.list.clear()
        for video in videos[:LIST_LIMIT]:
            video = self._library.validate_local(video)
            item = QListWidgetItem()
            item.setData(Qt.UserRole, video.id)
            widget = _Row(self._tokens, video, self._library.thumbnail_path(video), video_state(video))
            item.setSizeHint(QSize(widget.sizeHint().width(), THUMB_H + 12))
            self.list.addItem(item)
            self.list.setItemWidget(item, widget)
            item.setToolTip(video.title)
        self.list.blockSignals(False)
        shown, total = min(len(videos), LIST_LIMIT), len(videos)
        self.count_label.setText(self._tr.t("library.list_count", shown=shown, total=total) if shown < total else self._tr.t("library.list_total", total=total))
        self.set_current(self._current)

    def _activated(self, item):
        video_id = item.data(Qt.UserRole)
        self._current = video_id
        self.video_opened.emit(video_id)

    def retranslate(self):
        self.search.setPlaceholderText(self._tr.t("topbar.search_placeholder"))
        self.search.setAccessibleName(self._tr.t("topbar.search_placeholder"))
        self.mark_dirty()
