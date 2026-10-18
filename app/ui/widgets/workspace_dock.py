from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QStackedWidget, QToolButton, QVBoxLayout,
)

from app.styles.icons import icon
from app.ui.widgets.library_list import PANE_WIDTH, LibraryList
from app.ui.widgets.queue_panel import QueuePanel

TABS = (("library", "library", "dock.library"), ("queue", "queue", "dock.queue"), ("notes", "notes", "dock.notes"))


class NotesIndex(QFrame):
    """Lista dos vídeos que têm anotações (com a primeira linha de cada uma): clicar abre o vídeo."""

    video_opened = Signal(int)

    def __init__(self, translator, library):
        super().__init__()
        self.setObjectName("notesIndex")
        self._tr = translator
        self._library = library
        self._dirty = True
        column = QVBoxLayout(self)
        column.setContentsMargins(8, 10, 8, 8)
        column.setSpacing(8)
        self.list = QListWidget()
        self.list.setObjectName("libraryListView")
        self.list.setFrameShape(QFrame.NoFrame)
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.itemActivated.connect(self._opened)
        self.list.itemClicked.connect(self._opened)
        column.addWidget(self.list, 1)
        self.empty_label = QLabel()
        self.empty_label.setObjectName("cardMeta")
        self.empty_label.setWordWrap(True)
        column.addWidget(self.empty_label)
        library.notes_changed.connect(lambda _id: self.mark_dirty())
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

    def refresh(self):
        self._dirty = False
        self.list.clear()
        if not self._library.ready:
            return
        videos = [v for v in self._library.store.list_videos() if (v.notes or "").strip()]
        videos.sort(key=lambda v: (v.title or "").casefold())
        for video in videos:
            first = next((line.strip() for line in video.notes.splitlines() if line.strip()), "")
            item = QListWidgetItem(f"{video.title}\n{first[:90]}")
            item.setData(Qt.UserRole, video.id)
            item.setToolTip(video.notes[:400])
            self.list.addItem(item)
        self.empty_label.setVisible(not videos)

    def _opened(self, item):
        self.video_opened.emit(item.data(Qt.UserRole))

    def retranslate(self):
        self.empty_label.setText(self._tr.t("dock.notes_empty"))
        self.mark_dirty()


class WorkspaceDock(QFrame):
    """Painel esquerdo da Estação de trabalho, com três abas: Biblioteca, Fila e Notas (estilo painel lateral de um editor)."""

    video_opened = Signal(int)
    queue_remove_requested = Signal(int)
    queue_order_changed = Signal(list)
    queue_clear_requested = Signal()
    queue_next_requested = Signal()
    queue_previous_requested = Signal()

    def __init__(self, translator, tokens, library, org):
        super().__init__()
        self.setObjectName("workspaceDock")
        self.setMinimumWidth(PANE_WIDTH - 60)
        self._tr = translator
        self._tokens = tokens
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        tabs = QFrame()
        tabs.setObjectName("dockTabs")
        row = QHBoxLayout(tabs)
        row.setContentsMargins(6, 4, 6, 0)
        row.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self.tab_buttons = {}
        for key, _icon, _label in TABS:
            button = QToolButton()
            button.setObjectName("dockTab")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            button.clicked.connect(lambda _=False, k=key: self.show_tab(k))
            self._group.addButton(button)
            self.tab_buttons[key] = button
            row.addWidget(button)
        row.addStretch(1)
        column.addWidget(tabs)
        self.stack = QStackedWidget()
        self.library = LibraryList(translator, tokens, library, org)
        self.queue = QueuePanel(translator, tokens)
        self.notes = NotesIndex(translator, library)
        for widget in (self.library, self.queue, self.notes):
            self.stack.addWidget(widget)
        column.addWidget(self.stack, 1)
        self.library.video_opened.connect(self.video_opened)
        self.notes.video_opened.connect(self.video_opened)
        self.queue.video_opened.connect(self.video_opened)
        self.queue.remove_requested.connect(self.queue_remove_requested)
        self.queue.order_changed.connect(self.queue_order_changed)
        self.queue.clear_requested.connect(self.queue_clear_requested)
        self.queue.next_requested.connect(self.queue_next_requested)
        self.queue.previous_requested.connect(self.queue_previous_requested)
        self._tabs_order = [key for key, _i, _l in TABS]
        self.show_tab("library")
        self.retranslate()

    def show_tab(self, key):
        self.stack.setCurrentIndex(self._tabs_order.index(key))
        self.tab_buttons[key].setChecked(True)

    @property
    def current_tab(self):
        return self._tabs_order[self.stack.currentIndex()]

    def set_tokens(self, tokens):
        self._tokens = tokens
        for key, icon_name, _label in TABS:
            self.tab_buttons[key].setIcon(icon(icon_name, tokens["text_primary"], 16))
        self.library.set_tokens(tokens)
        self.queue.set_tokens(tokens)

    def retranslate(self):
        for key, _icon, label_key in TABS:
            text = self._tr.t(label_key)
            self.tab_buttons[key].setText(" " + text)
            self.tab_buttons[key].setToolTip(text)
            self.tab_buttons[key].setAccessibleName(text)
        self.library.retranslate()
        self.queue.retranslate()
        self.notes.retranslate()
        self.set_tokens(self._tokens)
