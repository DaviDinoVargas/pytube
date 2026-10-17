from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from app.domain.errors import StorageError
from app.services import download_service as ds
from app.ui.errors import describe_error
from app.ui.pages.base import EmptyState, Page
from app.ui.widgets.download_row import DownloadRow


def display_order(tasks):
    """Ativas primeiro (mais antigas antes), depois as finalizadas (mais recentes antes)."""
    active = sorted((t for t in tasks if not t.finished), key=lambda t: t.id)
    done = sorted((t for t in tasks if t.finished), key=lambda t: -t.id)
    return active + done


class DownloadsPage(Page):
    key = "downloads"
    video_opened = Signal(int)
    message = Signal(str, bool)

    def __init__(self, translator, manager, library, tokens):
        super().__init__(translator)
        self._manager = manager
        self._library = library
        self._tokens = tokens
        self._rows = {}
        self._dirty = True

        self.clear_button = QPushButton()
        self.clear_button.setObjectName("secondary")
        self.clear_button.setCursor(Qt.PointingHandCursor)
        self.clear_button.clicked.connect(manager.clear_finished)
        top = QHBoxLayout()
        top.addStretch(1)
        top.addWidget(self.clear_button)
        self.body.addLayout(top)

        self.empty = EmptyState(translator, self.key)
        self.body.addWidget(self.empty)
        self.list_box = QWidget()
        self.list_layout = QVBoxLayout(self.list_box)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(10)
        self.body.addWidget(self.list_box)
        self.body.addStretch(1)

        manager.queue_changed.connect(self.mark_dirty)
        manager.task_changed.connect(self._on_task_changed)
        self.retranslate()

    # -- atualização -----------------------------------------------------------------
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

    def refresh(self):
        self._dirty = False
        tasks = display_order(self._manager.tasks())
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().setParent(None)
                item.widget().deleteLater()
        self._rows = {}
        for task in tasks:
            video = self._library.get(task.video_id)
            row = DownloadRow(self._tr, self._tokens, task, self._library.thumbnail_path(video) if video else None)
            row.cancel_requested.connect(self._manager.cancel)
            row.retry_requested.connect(self._retry)
            row.open_requested.connect(self.video_opened)
            row.remove_requested.connect(self._manager.remove)
            self.list_layout.addWidget(row)
            self._rows[task.id] = row
        self.empty.setVisible(not tasks)
        self.list_box.setVisible(bool(tasks))
        self.clear_button.setVisible(any(t.finished for t in tasks))

    def _on_task_changed(self, task_id):
        row = self._rows.get(task_id)
        task = self._manager.get(task_id)
        if row is not None and task is not None:
            row.update_from(task)

    def _retry(self, task_id):
        try:
            self._manager.retry(task_id)
        except StorageError as exc:
            self.message.emit(describe_error(self._tr, exc.code if exc.code != "duplicate" else "already_queued"), True)

    def retranslate(self):
        super().retranslate()
        if hasattr(self, "clear_button"):
            self.clear_button.setText(self._tr.t("downloads.clear"))
            self.empty.retranslate()
            self.mark_dirty()
