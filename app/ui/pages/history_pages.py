from PySide6.QtCore import QLocale, Qt, Signal
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from app.domain import history as h
from app.domain.states import video_state
from app.ui.pages.base import EmptyState, Page
from app.ui.pages.video_pages import VideoPage
from app.ui.widgets.video_row import VideoRow


class ContinuePage(VideoPage):
    """'Continuar assistindo': o que foi começado e não terminado, do mais recente ao mais antigo."""

    key = "continue"

    def __init__(self, translator, library, tokens, org, **kwargs):
        self._org = org
        super().__init__(translator, library, tokens, **kwargs)
        self._can_forget = True

    def videos(self):
        return self._org.query(h.SMART_PLAYLISTS["continue"])


class HistoryPage(Page):
    """Histórico: tudo que já foi reproduzido, agrupado por dia, com opção de limpar."""

    key = "history"
    video_opened = Signal(int)
    video_action = Signal(int, str)
    message = Signal(str, bool)

    def __init__(self, translator, library, tokens, org, progress, **options):
        super().__init__(translator)
        self._library, self._tokens, self._org, self._progress = library, tokens, org, progress
        self._options = options  # can_download, download_status, organize
        self._dirty = True
        self.clear_button = QPushButton()
        self.clear_button.setObjectName("secondary")
        self.clear_button.setCursor(Qt.PointingHandCursor)
        self.clear_button.clicked.connect(self.clear)
        self.body.addWidget(self.clear_button, 0, Qt.AlignRight)
        self.empty = EmptyState(translator, self.key)
        self.body.addWidget(self.empty)
        self.list_box = QWidget()
        self.list_layout = QVBoxLayout(self.list_box)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(8)
        self.body.addWidget(self.list_box)
        self.body.addStretch(1)
        self.rows = []
        self.headings = []
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

    def _day_label(self, key):
        t = self._tr.t
        if key in ("today", "yesterday", "unknown"):
            return t(f"history.{key}")
        locale = QLocale("pt_BR" if self._tr.language == "pt-BR" else "en_US")
        return locale.toString(key, QLocale.LongFormat)

    def refresh(self):
        self._dirty = False
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().setParent(None)
                item.widget().deleteLater()
        self.rows, self.headings = [], []
        entries = h.history_entries(self._org.load_data()) if self._library.ready else []
        for key, group in h.group_by_day(entries):
            heading = QLabel(self._day_label(key))
            heading.setObjectName("sectionTitle")
            self.list_layout.addWidget(heading)
            self.headings.append(heading)
            for entry in group:
                self.list_layout.addWidget(self._make_row(entry))
        self.empty.setVisible(not entries)
        self.list_box.setVisible(bool(entries))
        self.clear_button.setVisible(bool(entries))

    def _make_row(self, entry):
        video = self._library.validate_local(entry.video)
        row = VideoRow(
            self._tr, self._tokens, video, video_state(video, self._options["download_status"](video.id)),
            self._library.thumbnail_path(video), can_download=self._options["can_download"](),
            organize=self._options["organize"], watch=h.watch_status(entry.progress),
            fraction=h.progress_fraction(video, entry.progress), can_forget=True,
        )
        row.open_requested.connect(self.video_opened)
        row.action_requested.connect(self.video_action)
        self.rows.append(row)
        return row

    def clear(self):
        if not self._library.ready or not self._confirm():
            return
        self._progress.clear_all()
        self.message.emit(self._tr.t("history.cleared_toast"), False)

    def _confirm(self):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(self._tr.t("history.confirm_title"))
        box.setText(self._tr.t("history.confirm_body"))
        ok = box.addButton(self._tr.t("history.clear"), QMessageBox.AcceptRole)
        box.addButton(self._tr.t("storage.cancel"), QMessageBox.RejectRole)
        box.exec()
        return box.clickedButton() is ok

    def retranslate(self):
        super().retranslate()
        if hasattr(self, "clear_button"):
            self.clear_button.setText(self._tr.t("history.clear"))
            self.empty.retranslate()
            self.mark_dirty()
