import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.domain import states
from app.domain import layouts, recommend
from app.domain.history import SMART_PLAYLISTS, progress_fraction, watch_status
from app.domain.query import LibraryQuery, apply_query
from app.domain.states import format_duration
from app.domain.states import video_state
from app.ui.pages.base import EmptyState, Page
from app.ui.pages.categories_page import CollectionCard, count_text
from app.ui.widgets.hero_banner import HeroBanner
from app.ui.widgets.poster_tile import STREAMING as TILE_STREAMING, WALL as TILE_WALL, PosterTile
from app.ui.widgets.thumb_row import ThumbRow, link_button, title_label
from app.ui.widgets.video_card import VideoCard
from app.ui.widgets.video_grid import VideoGrid

SECTION_LIMIT = 8
ROW_LIMIT = 14  # itens por fileira no layout Streaming
HERO_HEIGHT_FULL = 380


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

    def make_tile(self, video, mode=TILE_STREAMING):
        """Pôster sem moldura (layouts Streaming e Cinema), com as mesmas ações do cartão."""
        video = self._library.validate_local(video)
        watch, fraction = self.watch_info(video)
        tile = PosterTile(
            self._tr, self._tokens, video, video_state(video, self._download_status(video.id)), self._library.thumbnail_path(video),
            can_download=self._can_download(), organize=self._organize, watch=watch, fraction=fraction,
            can_forget=self._can_forget, mode=mode,
        )
        tile.open_requested.connect(self.video_opened)
        tile.action_requested.connect(self.video_action)
        return tile

    def make_wall(self, videos):
        grid = VideoGrid(gap=10)
        grid.set_cards([self.make_tile(v, TILE_WALL) for v in videos])
        return grid

    def make_posters(self, videos):
        grid = VideoGrid(gap=18)
        grid.set_cards([self.make_tile(v, TILE_STREAMING) for v in videos])
        return grid

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
    playlist_opened = Signal(int)

    def __init__(self, *args, org=None, **kwargs):
        self._org = org
        self._variant = layouts.HOME_CATEGORIES
        super().__init__(*args, **kwargs)

    def videos(self):
        return self._library.list_videos()

    def set_layout(self, profile):
        if profile.home != self._variant:
            self._variant = profile.home
            self._frame_for_variant()
            self.mark_dirty()

    def _frame_for_variant(self):
        """Streaming e Cinema abrem sem título de página e com o destaque ou o mural até a borda da janela."""
        bare = self._variant in (layouts.HOME_STREAMING, layouts.HOME_WALL)
        self.title.setVisible(not bare)
        self.subtitle.setVisible(not bare)
        root = self.layout()
        root.setContentsMargins(*((0, 0, 0, 0) if bare else (32, 28, 24, 0)))
        self.body.setContentsMargins(*((0, 0, 0, 24) if bare else (0, 0, 8, 16)))

    def render(self, videos):
        self._clear_body()
        self.empty.setVisible(not videos)
        if not videos:
            return
        self._frame_for_variant()
        if self._variant == layouts.HOME_STREAMING and self._org is not None:
            self._render_streaming()
            return
        if self._variant == layouts.HOME_WALL and self._org is not None:
            self._render_wall()
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

    # -- layout Streaming: destaque, fileiras horizontais e recomendações locais -------------------
    def _render_streaming(self):
        t = self._tr.t
        data = self._org.load_data()
        featured = recommend.featured(data)
        if featured is not None:
            self.body.addWidget(self._hero(featured, data))
        rows = []
        in_progress = apply_query(SMART_PLAYLISTS["continue"], data)
        if in_progress:
            rows.append((t("stream.row_continue"), in_progress, False, None))
        rows.append((t("home.section_recent"), apply_query(LibraryQuery(), data), False, None))
        ready = [v for v in apply_query(SMART_PLAYLISTS["unwatched"], data) if self._library.validate_local(v).local_status == "ok"]
        if ready:
            rows.append((t("stream.row_ready"), ready, False, None))
        base, because = recommend.because_you_watched(data, ROW_LIMIT)
        if base is not None:
            rows.append((t("stream.row_because", title=base.title), because, False, None))
        for title, items, rich, category in rows:
            self.body.addWidget(self._padded(self._row(title, items[:ROW_LIMIT], rich, category)))
        playlists = self._org.playlists()
        if playlists:
            self.body.addWidget(self._padded(self._playlist_row(playlists)))
        for category in data.categories:
            items = apply_query(LibraryQuery(category_ids=frozenset({category.id})), data)
            if items:
                self.body.addWidget(self._padded(self._row(category.name, items[:ROW_LIMIT], False, category)))
        self.body.addStretch(1)

    @staticmethod
    def _padded(widget, side=36):
        """Fileiras têm margem lateral; o destaque do Streaming e o mural do Cinema vão até a borda."""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(side, 0, side, 0)
        lay.addWidget(widget)
        return box

    # -- layout Cinema: mural de pôsteres ----------------------------------------------------------------
    def _render_wall(self):
        t = self._tr.t
        data = self._org.load_data()
        in_progress = apply_query(SMART_PLAYLISTS["continue"], data)
        if in_progress:
            heading = title_label(t("stream.row_continue"))
            row = ThumbRow(self._tokens, heading, [self.make_tile(v, TILE_WALL) for v in in_progress[:ROW_LIMIT]], None,
                           t("stream.prev"), t("stream.next"))
            self.body.addWidget(self._padded(row, 28))
        everything = apply_query(LibraryQuery(), data)
        box = QWidget()
        column = QVBoxLayout(box)
        column.setContentsMargins(28, 0, 28, 0)
        column.setSpacing(12)
        column.addWidget(title_label(t("wall.collection", count=len(everything))))
        column.addWidget(self.make_wall(everything))
        self.body.addWidget(box)
        self.body.addStretch(1)

    def _hero(self, video, data):
        t = self._tr.t
        position = recommend.resume_label_position(video, data)
        button = t("stream.continue_from", time=format_duration(position)) if position else t("stream.watch")
        meta = " · ".join(x for x in (video.channel, format_duration(video.duration)) if x)
        hero = HeroBanner(
            self._tokens, video, self._library.thumbnail_path(video), t("stream.featured"), meta, button,
            radius=0, height=HERO_HEIGHT_FULL, margin=36,  # sem moldura: vai de ponta a ponta, como em um serviço de streaming
        )
        hero.open_requested.connect(self.video_opened)
        return hero

    def _row(self, title, items, rich, category):
        cards = [self.make_tile(v, TILE_STREAMING) for v in items]
        if category is not None and category.color:
            heading = title_label(f'<span style="color:{category.color}">●</span> {html.escape(category.name)}', rich=True)
        else:
            heading = title_label(title)
        see_all = None
        if category is not None:
            see_all = link_button(self._tr.t("home.see_all"), lambda _=False, cid=category.id: self.category_all_requested.emit(cid))
        return ThumbRow(self._tokens, heading, cards, see_all, self._tr.t("stream.prev"), self._tr.t("stream.next"))

    def _playlist_row(self, playlists):
        counts = self._org.playlist_counts()
        cards = []
        for playlist in playlists[:ROW_LIMIT]:
            count = counts.get(playlist.id, 0)
            card = CollectionCard(
                self._tr, self._tokens, playlist.id, playlist.name, playlist.description,
                count_text(self._tr, count), None, menu=False,
            )
            card.opened.connect(self.playlist_opened)
            cards.append(card)
        return ThumbRow(self._tokens, title_label(self._tr.t("stream.row_playlists")), cards, None, self._tr.t("stream.prev"), self._tr.t("stream.next"))
