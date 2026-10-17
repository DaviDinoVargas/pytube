import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.domain import states
from app.domain.history import SMART_PLAYLISTS, progress_fraction, watch_status
from app.domain.query import LibraryQuery
from app.domain.states import video_state
from app.ui.pages.base import EmptyState, Page
from app.ui.widgets.video_card import VideoCard
from app.ui.widgets.video_grid import VideoGrid

SECTION_LIMIT = 8


class VideoPage(Page):
    """Página que lista cards. Atualiza só quando está visível; se não, marca para atualizar ao aparecer."""

    video_opened = Signal(int)
    video_action = Signal(int, str)

    def __init__(self, translator, library, tokens, can_download=lambda: False, download_status=lambda video_id: None, organize=None, progress=None):
        super().__init__(translator)
        self._library = library
        self._progress = progress
        self._can_forget = False
        self._organize = organize
        self._download_status = download_status
        self._tokens = tokens
        self._can_download = can_download
        self._dirty = True
        self.empty = EmptyState(translator, self.key)
        self.body.addWidget(self.empty)
        self.retranslate()

    # -- dados -------------------------------------------------------------------
    def videos(self):
        raise NotImplementedError

    def watch_info(self, video):
        """(status de assistido, fração 0..1) do vídeo, a partir do progresso salvo."""
        progress = self._progress.get(video.id) if self._progress is not None else None
        return watch_status(progress), progress_fraction(video, progress)

    def make_card(self, video):
        video = self._library.validate_local(video)
        watch, fraction = self.watch_info(video)
        card = VideoCard(
            self._tr,
            self._tokens,
            video,
            video_state(video, self._download_status(video.id)),
            self._library.thumbnail_path(video),
            can_download=self._can_download(),
            organize=self._organize,
            watch=watch,
            fraction=fraction,
            can_forget=self._can_forget,
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
    category_all_requested = Signal(int)

    def __init__(self, *args, org=None, **kwargs):
        self._org = org
        super().__init__(*args, **kwargs)

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
            self.body.addWidget(self._section(self._tr.t(key), items))
        for category in (self._org.categories() if self._org is not None else []):
            items = self._org.query(LibraryQuery(category_ids=frozenset({category.id})))
            if items:  # categorias vazias não ocupam espaço
                self.body.addWidget(self._section(category.name, items[:SECTION_LIMIT], category))
        self.body.addStretch(1)

    def _section(self, title, items, category=None):
        box = QWidget()
        column = QVBoxLayout(box)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(10)
        head = QHBoxLayout()
        heading = QLabel()
        heading.setObjectName("sectionTitle")
        if category is not None and category.color:
            heading.setTextFormat(Qt.RichText)  # o ponto leva a cor da categoria; o nome é escapado
            heading.setText(f'<span style="color:{category.color}">●</span> {html.escape(category.name)}')
        else:
            heading.setText(title)
        head.addWidget(heading)
        head.addStretch(1)
        if category is not None:
            more = QPushButton(self._tr.t("home.see_all"))
            more.setObjectName("linkButton")
            more.setCursor(Qt.PointingHandCursor)
            more.clicked.connect(lambda _=False, cid=category.id: self.category_all_requested.emit(cid))
            head.addWidget(more)
        column.addLayout(head)
        column.addWidget(self.make_grid(items))
        return box
