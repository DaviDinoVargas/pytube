from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout

from app.domain import states
from app.domain.states import video_state
from app.ui.pages.base import EmptyState, Page
from app.ui.widgets.video_card import VideoCard
from app.ui.widgets.video_grid import VideoGrid

SECTION_LIMIT = 8


class VideoPage(Page):
    """Página que lista cards. Atualiza só quando está visível; se não, marca para atualizar ao aparecer."""

    video_opened = Signal(int)
    video_action = Signal(int, str)

    def __init__(self, translator, library, tokens, can_download=lambda: False):
        super().__init__(translator)
        self._library = library
        self._tokens = tokens
        self._can_download = can_download
        self._dirty = True
        self.empty = EmptyState(translator, self.key)
        self.body.addWidget(self.empty)
        self.retranslate()

    # -- dados -------------------------------------------------------------------
    def videos(self):
        raise NotImplementedError

    def make_card(self, video):
        video = self._library.validate_local(video)
        card = VideoCard(
            self._tr,
            self._tokens,
            video,
            video_state(video),
            self._library.thumbnail_path(video),
            can_download=self._can_download(),
        )
        card.open_requested.connect(self.video_opened)
        card.action_requested.connect(self.video_action)
        return card

    def make_grid(self, videos):
        grid = VideoGrid()
        grid.set_cards([self.make_card(v) for v in videos])
        return grid

    # -- atualização --------------------------------------------------------------
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

    def retranslate(self):
        super().retranslate()
        if hasattr(self, "empty"):
            self.empty.retranslate()
            self.mark_dirty()

    def refresh(self):
        self._dirty = False
        self.render(self.videos())

    def render(self, videos):
        self._clear_body()
        self.empty.setVisible(not videos)
        if videos:
            self.body.addWidget(self.make_grid(videos))
            self.body.addStretch(1)

    def _clear_body(self):
        while self.body.count() > 1:  # o item 0 é o estado vazio
            item = self.body.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def cards(self):
        return [c for g in self.findChildren(VideoGrid) for c in g.cards]


class LibraryPage(VideoPage):
    key = "library"

    def videos(self):
        return self._library.list_videos()


class DownloadedPage(VideoPage):
    key = "downloaded"

    def videos(self):
        out = []
        for video in self._library.list_videos():
            if video_state(self._library.validate_local(video)) == states.DOWNLOADED:
                out.append(video)
        return out


class HomePage(VideoPage):
    key = "home"

    def videos(self):
        return self._library.list_videos()

    def render(self, videos):
        self._clear_body()
        self.empty.setVisible(not videos)
        if not videos:
            return
        sections = [("home.section_recent", videos[:SECTION_LIMIT])]
        downloaded = [v for v in videos if self._library.validate_local(v).local_status == "ok"]
        if downloaded:
            sections.append(("home.section_downloaded", downloaded[:SECTION_LIMIT]))
        for key, items in sections:
            box = QWidget()
            column = QVBoxLayout(box)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(10)
            heading = QLabel(self._tr.t(key))
            heading.setObjectName("sectionTitle")
            column.addWidget(heading)
            column.addWidget(self.make_grid(items))
            self.body.addWidget(box)
        self.body.addStretch(1)
