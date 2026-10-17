from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QTransform
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QToolButton, QVBoxLayout, QWidget

from app.domain.states import format_duration
from app.styles.icons import icon
from app.ui.pages.base import EmptyState, Page
from app.ui.pages.categories_page import CollectionCard, CollectionPage, count_text
from app.ui.widgets.video_card import cover_pixmap, format_added

ROW_THUMB = (96, 54)


class PlaylistsPage(CollectionPage):
    key = "playlists"
    new_key = "playlists.new"
    playlist_opened = Signal(int)
    play_requested = Signal(int)

    def items(self):
        return self._org.playlists()

    def make_card(self, playlist):
        counts = self._org.playlist_counts()
        count = counts.get(playlist.id, 0)
        card = CollectionCard(
            self._tr, self._tokens, playlist.id, playlist.name, playlist.description, count_text(self._tr, count),
            None, "playlists.rename", "playlists.delete", play=count > 0,
        )
        card.opened.connect(self.playlist_opened)
        card.edit_requested.connect(self._rename)
        card.delete_requested.connect(self._delete)
        card.play_requested.connect(self.play_requested)
        return card

    def _rename(self, playlist_id):
        playlist = self._org.get_playlist(playlist_id)
        if playlist is not None:
            self._prompt(playlist)

    def _delete(self, playlist_id):
        playlist = self._org.get_playlist(playlist_id)
        if playlist is not None and self._confirm("playlists.confirm_title", "playlists.confirm_body", playlist.name, "playlists.delete"):
            self._org.delete_playlist(playlist_id)  # só a playlist: vídeos e arquivos ficam


class PlaylistItemRow(QFrame):
    open_requested = Signal(int)
    move_requested = Signal(int, int)  # id do vídeo, deslocamento (-1 sobe, +1 desce)
    remove_requested = Signal(int)

    def __init__(self, translator, tokens, video, index, total, thumb_path):
        super().__init__()
        self.video = video
        self.setObjectName("videoRow")
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        t = translator.t
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 6, 8)
        row.setSpacing(12)
        number = QLabel(str(index + 1))
        number.setObjectName("cardMeta")
        number.setFixedWidth(22)
        number.setAlignment(Qt.AlignCenter)
        row.addWidget(number)
        thumb = QLabel()
        thumb.setFixedSize(*ROW_THUMB)
        thumb.setPixmap(cover_pixmap(thumb_path, ROW_THUMB[0], ROW_THUMB[1], 8, tokens))
        row.addWidget(thumb)
        column = QVBoxLayout()
        column.setSpacing(2)
        title = QLabel(video.title or video.url)
        title.setObjectName("cardTitle")
        meta = " · ".join(p for p in (video.channel, format_duration(video.duration)) if p)
        info = QLabel(meta)
        info.setObjectName("cardMeta")
        column.addWidget(title)
        column.addWidget(info)
        row.addLayout(column, 1)
        self.buttons = {}
        for key, icon_name, slot, enabled in (
            ("move_up", "back", lambda: self.move_requested.emit(self.video.id, -1), index > 0),
            ("move_down", "back", lambda: self.move_requested.emit(self.video.id, 1), index < total - 1),
            ("remove", "trash", lambda: self.remove_requested.emit(self.video.id), True),
        ):
            button = QToolButton()
            button.setObjectName("iconButton")
            button.setIconSize(QSize(20, 20))
            base = icon(icon_name, tokens["text_secondary"])
            angle = {"move_up": 90, "move_down": -90}.get(key)  # a seta "voltar" girada aponta para cima/baixo
            button.setIcon(QIcon(base.pixmap(20, 20).transformed(QTransform().rotate(angle))) if angle else base)
            button.setToolTip(t(f"playlist.{key}"))
            button.setAccessibleName(t(f"playlist.{key}"))
            button.setEnabled(enabled)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(slot)
            row.addWidget(button)
            self.buttons[key] = button

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.open_requested.emit(self.video.id)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.open_requested.emit(self.video.id)
            return
        super().keyPressEvent(event)


class PlaylistDetailPage(Page):
    """Uma playlist: vídeos na ordem escolhida, com subir/descer/remover e 'Reproduzir tudo'."""

    key = "playlist"
    back_requested = Signal()
    play_requested = Signal(int, int)  # playlist, vídeo inicial (0 = o primeiro)
    video_opened = Signal(int)

    def __init__(self, translator, org, library, tokens):
        super().__init__(translator)
        self._org, self._library, self._tokens = org, library, tokens
        self._playlist_id = None
        self._dirty = True
        self.back_button = QToolButton()
        self.back_button.setObjectName("textButton")
        self.back_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.back_button.setIconSize(QSize(18, 18))
        self.back_button.setCursor(Qt.PointingHandCursor)
        self.back_button.clicked.connect(self.back_requested)
        self.play_all = QPushButton()
        self.play_all.setObjectName("primary")
        self.play_all.setCursor(Qt.PointingHandCursor)
        self.play_all.clicked.connect(lambda: self.play_requested.emit(self._playlist_id, 0))
        top = QHBoxLayout()
        top.addWidget(self.back_button)
        top.addStretch(1)
        top.addWidget(self.play_all)
        self.body.addLayout(top)
        self.empty = EmptyState(translator, "playlist")
        self.body.addWidget(self.empty)
        self.list_box = QWidget()
        self.list_layout = QVBoxLayout(self.list_box)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(8)
        self.body.addWidget(self.list_box)
        self.body.addStretch(1)
        self.rows = []
        self.retranslate()

    @property
    def playlist_id(self):
        return self._playlist_id

    def show_playlist(self, playlist_id):
        self._playlist_id = playlist_id
        self.refresh()

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
        playlist = self._org.get_playlist(self._playlist_id) if self._playlist_id is not None else None
        for row in self.rows:
            row.setParent(None)
            row.deleteLater()
        self.rows = []
        if playlist is None:
            self.title.setText("")
            self.subtitle.setText("")
            self.empty.setVisible(False)
            self.play_all.setVisible(False)
            return
        videos = self._org.playlist_videos(playlist.id)
        self.title.setText(playlist.name)
        self.subtitle.setText(playlist.description or count_text(self._tr, len(videos)))
        for index, video in enumerate(videos):
            row = PlaylistItemRow(self._tr, self._tokens, video, index, len(videos), self._library.thumbnail_path(video))
            row.open_requested.connect(lambda vid, pid=playlist.id: self.play_requested.emit(pid, vid))
            row.move_requested.connect(self._move)
            row.remove_requested.connect(self._remove)
            self.list_layout.addWidget(row)
            self.rows.append(row)
        self.empty.setVisible(not videos)
        self.list_box.setVisible(bool(videos))
        self.play_all.setVisible(bool(videos))

    def _move(self, video_id, delta):
        items = self._org.playlist_video_ids(self._playlist_id)
        if video_id in items:
            self._org.move_in_playlist(self._playlist_id, video_id, items.index(video_id) + delta)

    def _remove(self, video_id):
        self._org.remove_from_playlist(self._playlist_id, [video_id])

    def set_tokens(self, tokens):
        self._tokens = tokens
        self.back_button.setIcon(icon("back", tokens["text_primary"], 18))
        self.mark_dirty()

    def retranslate(self):
        t = self._tr.t
        if hasattr(self, "play_all"):
            self.back_button.setText(" " + t("playlist.back"))
            self.play_all.setText(t("playlists.play_all"))
            self.empty.retranslate()
            self.mark_dirty()
