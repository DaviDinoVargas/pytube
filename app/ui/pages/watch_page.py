import re

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.domain import states
from app.domain.states import format_duration, video_state
from app.infrastructure.providers.base import ProviderError, VideoInfo
from app.services.storage_service import format_bytes
from app.styles.icons import icon
from app.ui.pages.base import Page
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

    def __init__(self, translator, library, tokens):
        super().__init__(translator)
        self._library = library
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

        self.retranslate()

    # -- ciclo de vida ------------------------------------------------------------
    def open_source_id(self, source_id):
        """Abre um vídeo pelo id. Se já está na biblioteca, não consulta a rede."""
        self._last_id = source_id
        self._request += 1
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
            self._show_video(video)

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
