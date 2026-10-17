from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QToolButton, QVBoxLayout,
)

from app.domain.states import format_duration
from app.styles.icons import icon


class QueuePanel(QFrame):
    """Fila de reprodução: arraste para reordenar, Enter ou duplo clique toca, Delete remove. O item que toca vai em negrito."""

    video_opened = Signal(int)
    remove_requested = Signal(int)
    order_changed = Signal(list)
    clear_requested = Signal()
    next_requested = Signal()
    previous_requested = Signal()

    def __init__(self, translator, tokens):
        super().__init__()
        self.setObjectName("queuePanel")
        self._tr = translator
        self._tokens = tokens
        self._current = None
        column = QVBoxLayout(self)
        column.setContentsMargins(14, 10, 14, 12)
        column.setSpacing(8)
        head = QHBoxLayout()
        head.setSpacing(4)
        self.title_label = QLabel()
        self.title_label.setObjectName("groupTitle")
        self.previous_button = self._button(self.previous_requested)
        self.next_button = self._button(self.next_requested)
        head.addWidget(self.title_label)
        head.addStretch(1)
        head.addWidget(self.previous_button)
        head.addWidget(self.next_button)
        column.addLayout(head)
        self.list = QListWidget()
        self.list.setObjectName("queueList")
        self.list.setFrameShape(QFrame.NoFrame)
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setDefaultDropAction(Qt.MoveAction)
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.setMinimumHeight(110)
        self.list.itemActivated.connect(self._activated)
        self.list.itemDoubleClicked.connect(self._activated)
        self.list.model().rowsMoved.connect(lambda *_: self.order_changed.emit(self.ids()))
        column.addWidget(self.list, 1)
        self.empty_label = QLabel()
        self.empty_label.setObjectName("cardMeta")
        self.empty_label.setWordWrap(True)
        column.addWidget(self.empty_label)
        foot = QHBoxLayout()
        self.remove_button = QPushButton()
        self.remove_button.setObjectName("linkButton")
        self.remove_button.setCursor(Qt.PointingHandCursor)
        self.remove_button.clicked.connect(self._remove_selected)
        self.clear_button = QPushButton()
        self.clear_button.setObjectName("linkButton")
        self.clear_button.setCursor(Qt.PointingHandCursor)
        self.clear_button.clicked.connect(self.clear_requested)
        foot.addWidget(self.remove_button)
        foot.addStretch(1)
        foot.addWidget(self.clear_button)
        column.addLayout(foot)
        self.retranslate()

    def _button(self, signal):
        button = QToolButton()
        button.setObjectName("iconButton")
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(signal)
        return button

    # -- dados ------------------------------------------------------------------------------------
    def ids(self):
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]

    def set_queue(self, videos, current):
        self._current = current
        selected = self._selected_id()
        self.list.blockSignals(True)
        self.list.clear()
        for position, video in enumerate(videos, 1):
            duration = format_duration(video.duration)
            playing = video.id == current
            item = QListWidgetItem(f"{'▶ ' if playing else ''}{position}. {video.title}" + (f"  ·  {duration}" if duration else ""))
            item.setData(Qt.UserRole, video.id)
            item.setToolTip(video.title)
            if playing:
                font = QFont(item.font())
                font.setBold(True)
                item.setFont(font)
            self.list.addItem(item)
            if video.id == selected:
                self.list.setCurrentItem(item)
        self.list.blockSignals(False)
        empty = not videos
        self.list.setVisible(not empty)
        self.empty_label.setVisible(empty)
        for button in (self.previous_button, self.next_button, self.remove_button, self.clear_button):
            button.setEnabled(not empty)
        self.title_label.setText(self._tr.t("queue.title_count", count=len(videos)).upper())

    def _selected_id(self):
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item is not None else None

    def _activated(self, item):
        self.video_opened.emit(item.data(Qt.UserRole))

    def _remove_selected(self):
        video_id = self._selected_id()
        if video_id is not None:
            self.remove_requested.emit(video_id)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self._remove_selected()
            return
        super().keyPressEvent(event)

    # -- tema e idioma --------------------------------------------------------------------------------
    def set_tokens(self, tokens):
        self._tokens = tokens
        self.previous_button.setIcon(icon("skip_back", tokens["text_primary"], 18))
        self.next_button.setIcon(icon("skip_next", tokens["text_primary"], 18))

    def retranslate(self):
        t = self._tr.t
        self.title_label.setText(t("queue.title_count", count=self.list.count()).upper())
        for button, key in ((self.previous_button, "queue.previous"), (self.next_button, "queue.next")):
            button.setToolTip(t(key))
            button.setAccessibleName(t(key))
        self.remove_button.setText(t("queue.remove"))
        self.clear_button.setText(t("queue.clear"))
        self.empty_label.setText(t("queue.empty"))
        self.list.setAccessibleName(t("queue.title"))
        self.set_tokens(self._tokens)
