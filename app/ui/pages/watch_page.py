import re

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.domain import states
from app.domain.errors import DuplicateError, StorageError
from app.domain.states import format_duration, video_state
from app.infrastructure.providers import quality
from app.infrastructure.providers.base import ProviderError, VideoInfo
from app.services import download_service as ds
from app.services.storage_service import format_bytes
from app.styles.icons import icon
from app.ui.errors import describe_error
from app.ui.pages.base import Page
from app.ui.widgets.download_row import status_text
from app.ui.widgets.player_area import PlayerArea
from app.ui.widgets.video_card import format_added
from app.ui.workers import run_async

_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_LOADING, _ERROR, _CONTENT = 0, 1, 2
DESCRIPTION_LINES = 4


def watch_url(source_id):
    """Link seguro para o navegador, montado só a partir de um id validado."""
    return f"https://www.youtube.com/watch?v={source_id}" if _ID.match(source_id or "") else None


def info_from_video(video):
    return VideoInfo(
        source_id=video.source_id,
        url=video.url,
        title=video.title,
        channel=video.channel,
        duration=video.duration,
        description=video.description,
        source=video.source,
    )


class WatchPage(Page):
    """Tela de um vídeo: informações, salvar na biblioteca e abrir. O player embutido chega na etapa do player."""

    key = "watch"
    back_requested = Signal()
    message = Signal(str, bool)  # texto, é_erro

    def __init__(self, translator, library, tokens, downloads, consent=lambda: True):
        super().__init__(translator)
        self._library = library
        self._downloads = downloads
        self._consent = consent
        self._streams = None  # None: ainda não carregadas
        self._streams_error = False
        self._streams_token = 0
        self._player_height = None
        self._user_height = None  # só a escolha explícita do usuário; o padrão automático não conta
        self._tokens = tokens
        self._info = None
        self._video = None
        self._request = 0
        self._last_id = None
        self._description_open = False

        self.title.hide()
        self.subtitle.hide()
        self.back_button = QToolButton()
        self.back_button.setObjectName("textButton")
        self.back_button.setCursor(Qt.PointingHandCursor)
        self.back_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.back_button.setIconSize(QSize(18, 18))
        self.back_button.clicked.connect(self.back_requested)
        self.body.addWidget(self.back_button, 0, Qt.AlignLeft)

        self.stack = QStackedWidget()
        self.body.addWidget(self.stack, 1)

        # carregando
        loading = QWidget()
        lay = QVBoxLayout(loading)
        self.loading_label = QLabel()
        self.loading_label.setObjectName("emptyBody")
        self.loading_label.setAlignment(Qt.AlignCenter)
        lay.addStretch(1)
        lay.addWidget(self.loading_label)
        lay.addStretch(2)
        self.stack.addWidget(loading)

        # erro
        error = QWidget()
        lay = QVBoxLayout(error)
        self.error_label = QLabel()
        self.error_label.setObjectName("emptyTitle")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setWordWrap(True)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.retry_button = QPushButton()
        self.retry_button.setObjectName("primary")
        self.retry_button.clicked.connect(self.retry)
        self.error_browser_button = QPushButton()
        self.error_browser_button.setObjectName("secondary")
        self.error_browser_button.clicked.connect(self.open_in_browser)
        for b in (self.retry_button, self.error_browser_button):
            b.setCursor(Qt.PointingHandCursor)
            buttons.addWidget(b)
        buttons.addStretch(1)
        lay.addStretch(1)
        lay.addWidget(self.error_label)
        lay.addLayout(buttons)
        lay.addStretch(2)
        self.stack.addWidget(error)

        # conteúdo
        content = QWidget()
        col = QVBoxLayout(content)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(12)
        self.player = PlayerArea(translator, tokens)
        self.player.browser_requested.connect(self.open_in_browser)
        col.addWidget(self.player)
        self.title_label = QLabel()
        self.title_label.setObjectName("watchTitle")
        self.title_label.setWordWrap(True)
        self.meta_label = QLabel()
        self.meta_label.setObjectName("pageSubtitle")
        col.addWidget(self.title_label)
        col.addWidget(self.meta_label)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.save_button = QPushButton()
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.save_button.clicked.connect(self.toggle_saved)
        self.browser_button = QPushButton()
        self.browser_button.setObjectName("secondary")
        self.browser_button.setCursor(Qt.PointingHandCursor)
        self.browser_button.clicked.connect(self.open_in_browser)
        actions.addWidget(self.save_button)
        actions.addWidget(self.browser_button)
        actions.addStretch(1)
        col.addLayout(actions)

        self.local_label = QLabel()
        self.local_label.setObjectName("statusOk")
        col.addWidget(self.local_label)

        # download: qualidade + botão + andamento
        panel = QFrame()
        panel.setObjectName("card")
        panel.setMaximumWidth(1000)
        panel_lay = QVBoxLayout(panel)
        panel_lay.setContentsMargins(16, 12, 16, 12)
        panel_lay.setSpacing(8)
        pick = QHBoxLayout()
        pick.setSpacing(10)
        self.quality_label = QLabel()
        self.quality_label.setObjectName("fieldLabel")
        self.quality_combo = QComboBox()
        self.quality_combo.setMinimumWidth(190)
        self.quality_combo.activated.connect(lambda _i: setattr(self, "_user_height", self.quality_combo.currentData()))
        self.download_button = QPushButton()
        self.download_button.setObjectName("primary")
        self.download_button.setCursor(Qt.PointingHandCursor)
        self.download_button.clicked.connect(self.start_download)
        self.quality_retry = QPushButton()
        self.quality_retry.setObjectName("linkButton")
        self.quality_retry.setCursor(Qt.PointingHandCursor)
        self.quality_retry.clicked.connect(self._load_streams)
        pick.addWidget(self.quality_label)
        pick.addWidget(self.quality_combo)
        pick.addWidget(self.download_button)
        pick.addWidget(self.quality_retry)
        pick.addStretch(1)
        panel_lay.addLayout(pick)
        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_label = QLabel()
        self.progress_label.setObjectName("cardMeta")
        self.cancel_button = QToolButton()
        self.cancel_button.setObjectName("iconButton")
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        self.cancel_button.clicked.connect(self._cancel_download)
        progress_row.addWidget(self.progress_bar, 1)
        progress_row.addWidget(self.cancel_button)
        panel_lay.addLayout(progress_row)
        panel_lay.addWidget(self.progress_label)
        self.download_panel = panel
        col.addWidget(panel)

        card = QFrame()
        card.setObjectName("card")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(16, 12, 16, 12)
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.description_toggle = QPushButton()
        self.description_toggle.setObjectName("linkButton")
        self.description_toggle.setCursor(Qt.PointingHandCursor)
        self.description_toggle.clicked.connect(self._toggle_description)
        card_lay.addWidget(self.description_label)
        card_lay.addWidget(self.description_toggle, 0, Qt.AlignLeft)
        self.description_card = card
        card.setMaximumWidth(1000)
        col.addWidget(card, 0, Qt.AlignLeft)
        col.addStretch(1)
        self.stack.addWidget(content)

        downloads.task_changed.connect(self._on_task_changed)
        library.changed.connect(self._on_library_changed)
        self.retranslate()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # o player ocupa no máximo ~58% da altura: título, ações e download continuam à vista
        self.player.set_max_height(self.height() * 0.58)

    # -- ciclo de vida ------------------------------------------------------------
    def open_source_id(self, source_id):
        """Abre um vídeo pelo id. Se já está na biblioteca, não consulta a rede."""
        self._last_id = source_id
        self._request += 1
        self._reset_download_choice(source_id)
        video = self._library.find(source_id) if self._library.ready else None
        if video is not None:
            self._show_video(video)
            return
        self._info, self._video = None, None
        self.stack.setCurrentIndex(_LOADING)
        token = self._request
        run_async(
            lambda: self._library.fetch_info(source_id),
            lambda info: self._on_info(token, info),
            lambda exc: self._on_error(token, exc),
        )

    def open_saved(self, video_id):
        video = self._library.get(video_id)
        if video is not None:
            self._last_id = video.source_id
            self._request += 1
            self._reset_download_choice(video.source_id)
            self._show_video(video)

    def _reset_download_choice(self, source_id):
        if source_id != getattr(self._info, "source_id", None):
            self._user_height = None

    def retry(self):
        if self._last_id:
            self.open_source_id(self._last_id)

    def _on_info(self, token, info):
        if token != self._request:
            return  # o usuário já abriu outro vídeo
        self._info, self._video = info, None
        self._render()

    def _on_error(self, token, exc):
        if token != self._request:
            return
        code = exc.code if isinstance(exc, ProviderError) else "failed"
        text = self._tr.t(f"error.provider_{code}")
        self.error_label.setText(text if text != f"error.provider_{code}" else self._tr.t("error.unknown"))
        self.stack.setCurrentIndex(_ERROR)

    def _show_video(self, video):
        video = self._library.validate_local(video)
        self._video = video
        self._info = info_from_video(video)
        self._render()

    # -- renderização ---------------------------------------------------------------
    def _render(self):
        t = self._tr.t
        info = self._info
        self.title_label.setText(info.title)
        parts = [p for p in (info.channel, format_duration(info.duration)) if p]
        if self._video is not None:
            added = format_added(self._video.added_at, self._tr.language)
            if added:
                parts.append(t("card.added", date=added))
        self.meta_label.setText(" · ".join(parts))
        self.player.set_thumbnail(self._library.thumbnail_path(self._video) if self._video else None)
        self._render_actions()
        self._render_description()
        self._init_streams()
        self.stack.setCurrentIndex(_CONTENT)

    def _render_actions(self):
        t = self._tr.t
        saved = self._video is not None
        self.save_button.setText(t("watch.remove") if saved else t("watch.save"))
        self.save_button.setObjectName("secondary" if saved else "primary")
        self.save_button.setIcon(icon("trash" if saved else "bookmark", self._tokens["text_primary"] if saved else self._tokens["text_on_accent"], 18))
        self.save_button.style().unpolish(self.save_button)
        self.save_button.style().polish(self.save_button)
        self.save_button.setEnabled(self._library.ready)
        local = ""
        if saved and video_state(self._video) == states.DOWNLOADED:
            local = t(
                "watch.local_file",
                quality=self._video.local_quality or "—",
                size=format_bytes(self._video.local_size or 0),
            )
        self.local_label.setText(local)
        self.local_label.setVisible(bool(local))
        self._render_download()

    def _render_description(self):
        text = (self._info.description or "").strip()
        self.description_card.setVisible(True)
        if not text:
            self.description_label.setText(self._tr.t("watch.no_description"))
            self.description_toggle.hide()
            return
        lines = text.splitlines()
        long = len(lines) > DESCRIPTION_LINES or len(text) > 400
        if long and not self._description_open:
            text = "\n".join(lines[:DESCRIPTION_LINES])[:400].rstrip() + "…"
        self.description_label.setText(text)
        self.description_toggle.setVisible(long)
        self.description_toggle.setText(self._tr.t("watch.desc_less" if self._description_open else "watch.desc_more"))

    # -- download -----------------------------------------------------------------------
    def set_player_height(self, height):
        """Altura do player (v. player): a qualidade padrão do download acompanha o que está tocando."""
        self._player_height = height
        self._fill_quality_combo()

    def _init_streams(self):
        info = self._info
        self._streams = list(info.streams) if info is not None and info.streams else None
        self._streams_error = False
        self._fill_quality_combo()
        if self._streams is None and self._library.ready:
            self._load_streams()

    def _load_streams(self):
        if self._info is None:
            return
        self._streams_token += 1
        token, source_id = self._streams_token, self._info.source_id
        self._streams_error = False
        self._fill_quality_combo()
        run_async(
            lambda: self._library.fetch_info(source_id),
            lambda info: self._on_streams(token, info),
            lambda exc: self._on_streams_failed(token),
        )

    def _on_streams(self, token, info):
        if token != self._streams_token:
            return
        self._streams = list(info.streams)
        self._fill_quality_combo()

    def _on_streams_failed(self, token):
        if token != self._streams_token:
            return
        self._streams, self._streams_error = None, True
        self._fill_quality_combo()

    def _quality_text(self, height):
        streams = self._streams or []
        selection = None
        try:
            selection = quality.pick(streams, height)
        except ProviderError:
            pass
        label = selection.label if selection else f"{height}p"
        size = 0
        if selection:
            size = (selection.video.filesize or 0) + ((selection.audio.filesize or 0) if selection.audio else 0)
        return f"{label} · ~{format_bytes(size)}" if size else label

    def _fill_quality_combo(self):
        t = self._tr.t
        combo = self.quality_combo
        combo.blockSignals(True)
        combo.clear()
        if self._streams:
            heights = quality.available_heights(self._streams)
            for height in heights:
                combo.addItem(self._quality_text(height), height)
            wanted = self._user_height if self._user_height in heights else quality.default_height(self._streams, self._player_height)
            index = combo.findData(wanted)
            combo.setCurrentIndex(index if index >= 0 else 0)
            if not heights:
                combo.addItem(t("dl.no_qualities"), None)
        elif self._streams_error:
            combo.addItem(t("dl.no_qualities"), None)
        else:
            combo.addItem(t("dl.loading_qualities"), None)
        combo.blockSignals(False)
        self._render_download()

    def _current_task(self):
        if self._video is None:
            return None
        task = self._downloads.task_for_video(self._video.id)
        return task if task is not None and task.status in ds.ACTIVE else None

    def _render_download(self):
        t = self._tr.t
        has_height = self.quality_combo.currentData() is not None
        busy = self._current_task()
        downloaded = self._video is not None and video_state(self._video) == states.DOWNLOADED
        self.quality_label.setText(t("dl.quality"))
        self.download_button.setText(t("dl.button_again" if downloaded else "dl.button"))
        self.download_button.setIcon(icon("downloads", self._tokens["text_on_accent"], 18))
        self.quality_combo.setEnabled(has_height and busy is None)
        self.download_button.setEnabled(has_height and busy is None and self._library.ready)
        self.quality_retry.setVisible(self._streams_error)
        self.quality_retry.setText(t("watch.retry"))
        self.progress_bar.setVisible(busy is not None)
        self.progress_label.setVisible(busy is not None)
        self.cancel_button.setVisible(busy is not None)
        self.cancel_button.setIcon(icon("close", self._tokens["text_secondary"], 20))
        self.cancel_button.setToolTip(t("dl.cancel"))
        self.cancel_button.setAccessibleName(t("dl.cancel"))
        if busy is not None:
            self._render_progress(busy)

    def _render_progress(self, task):
        self.progress_label.setText(status_text(self._tr, task))
        if task.status in (ds.RESOLVING, ds.FINALIZING):
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 1000)
            self.progress_bar.setValue(int(task.progress * 1000))

    def _on_task_changed(self, task_id):
        task = self._downloads.get(task_id)
        if task is None or self._video is None or task.video_id != self._video.id:
            return
        if task.status in ds.ACTIVE:
            self._render_download()
        else:
            self._video = self._library.get(self._video.id) or self._video
            self._render_actions()
            if task.status == ds.FAILED:
                self.message.emit(describe_error(self._tr, task.error_code), True)

    def _on_library_changed(self):
        if self._video is None or self.stack.currentIndex() != _CONTENT:
            return
        fresh = self._library.get(self._video.id)
        if fresh is not None:
            self._video = fresh
            self._render_actions()

    def start_download(self):
        height = self.quality_combo.currentData()
        if height is None or self._info is None or not self._library.ready:
            return
        if not self._consent():
            return
        if self._video is None:  # baixar também guarda o vídeo na biblioteca
            info, token = self._info, self._request
            self.download_button.setEnabled(False)
            run_async(
                lambda: self._library.save_info(info),
                lambda result: self._saved_then_enqueue(token, result[0], height),
                lambda exc: self.message.emit(describe_error(self._tr, getattr(exc, "code", "")), True),
            )
            return
        self._enqueue(self._video.id, height)

    def _saved_then_enqueue(self, token, video, height):
        if token == self._request:
            self._show_video(video)
        self._enqueue(video.id, height)

    def _enqueue(self, video_id, height, replace=False):
        try:
            self._downloads.enqueue(video_id, height, replace=replace)
        except DuplicateError as exc:
            if "already_downloaded" in exc.detail and not replace:
                if self._confirm_download_again():
                    self._enqueue(video_id, height, replace=True)
                return
            self.message.emit(describe_error(self._tr, "already_queued"), True)
            return
        except StorageError as exc:
            self.message.emit(describe_error(self._tr, exc.code), True)
            return
        self.message.emit(self._tr.t("dl.queued_toast"), False)
        self._render_download()

    def _cancel_download(self):
        task = self._current_task()
        if task is not None:
            self._downloads.cancel(task.id)

    def _confirm_download_again(self):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(self._tr.t("dl.confirm_again_title"))
        box.setText(self._tr.t("dl.confirm_again_body"))
        ok = box.addButton(self._tr.t("dl.confirm_again_ok"), QMessageBox.AcceptRole)
        box.addButton(self._tr.t("storage.cancel"), QMessageBox.RejectRole)
        box.exec()
        return box.clickedButton() is ok

    def _toggle_description(self):
        self._description_open = not self._description_open
        self._render_description()

    # -- ações ------------------------------------------------------------------------
    def toggle_saved(self):
        if not self._library.ready or self._info is None:
            return
        if self._video is None:
            info = self._info
            self.save_button.setEnabled(False)
            token = self._request
            run_async(
                lambda: self._library.save_info(info),
                lambda result: self._on_saved(token, result),
                lambda exc: self._on_save_failed(token, exc),
            )
            return
        video = self._video
        if video_state(video) == states.DOWNLOADED and not self._confirm_remove(video):
            return
        self._library.remove(video.id)
        self._video = None
        self._render()
        self.message.emit(self._tr.t("watch.removed_toast"), False)

    def _on_saved(self, token, result):
        video, _created = result
        if token == self._request:
            self._show_video(video)
        self.message.emit(self._tr.t("watch.saved_toast"), False)

    def _on_save_failed(self, token, exc):
        if token == self._request:
            self._render_actions()
        self.message.emit(self._tr.t("error.unknown"), True)

    def _confirm_remove(self, video):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(self._tr.t("watch.confirm_remove_title"))
        box.setText(self._tr.t("watch.confirm_remove_body"))
        remove = box.addButton(self._tr.t("watch.remove"), QMessageBox.AcceptRole)
        box.addButton(self._tr.t("storage.cancel"), QMessageBox.RejectRole)
        box.exec()
        return box.clickedButton() is remove

    def open_in_browser(self):
        url = watch_url(self._last_id)
        if url:
            QDesktopServices.openUrl(QUrl(url))

    # -- tema e idioma ------------------------------------------------------------------
    def set_tokens(self, tokens):
        self._tokens = tokens
        self.player.set_tokens(tokens)
        self.back_button.setIcon(icon("back", tokens["text_primary"], 18))
        self.browser_button.setIcon(icon("external", tokens["text_primary"], 18))
        if self._info is not None:
            self._render_actions()
        else:
            self._render_download()

    def retranslate(self):
        t = self._tr.t
        self.back_button.setText(" " + t("watch.back"))
        self.loading_label.setText(t("watch.loading"))
        self.retry_button.setText(t("watch.retry"))
        self.error_browser_button.setText(t("watch.open_browser"))
        self.browser_button.setText(t("watch.open_browser"))
        self.player.retranslate()
        if self._info is not None:
            self._render()
