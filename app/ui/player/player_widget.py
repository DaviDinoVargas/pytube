from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)

from app.domain import playback
from app.domain.states import format_duration
from app.ui.errors import describe_error
from app.ui.player import shortcuts
from app.ui.player.controls import PlayerControls
from app.styles.icons import icon
from app.ui.player.local_player import LocalPlayer
from app.ui.workers import run_async

MAX_WIDTH = 1000
UNLIMITED = 16777215  # modo cinema: o player usa toda a largura que couber
MINI_WIDTH = 420
MINI_MARGIN = 24
SAVE_INTERVAL_MS = 5000
NOTICE_MS = 10000

SOURCE_LOCAL, SOURCE_ONLINE, SOURCE_STREAM = "local", "online", "stream"


def create_online_player():
    """Cria o player online sob demanda. Devolve None se o QtWebEngine não estiver instalado."""
    try:
        from app.ui.player.online_player import OnlinePlayer
    except Exception:
        return None
    return OnlinePlayer()


class PlayerMessage(QFrame):
    """Aviso sobre a área do vídeo, com as saídas possíveis em botões."""

    def __init__(self):
        super().__init__()
        self.setObjectName("playerMessage")
        column = QVBoxLayout(self)
        column.setAlignment(Qt.AlignCenter)
        column.setSpacing(12)
        self.label = QLabel()
        self.label.setObjectName("playerMessageText")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setMaximumWidth(560)
        column.addWidget(self.label, 0, Qt.AlignCenter)
        self.row = QHBoxLayout()
        self.row.setSpacing(10)
        self.row.setAlignment(Qt.AlignCenter)
        column.addLayout(self.row)
        self.buttons = []

    def show_message(self, text, actions=()):
        self.label.setText(text)
        while self.row.count():
            item = self.row.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.buttons = []
        for index, (label, callback) in enumerate(actions):
            button = QPushButton(label)
            button.setObjectName("primary" if index == 0 else "secondary")
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(callback)
            self.row.addWidget(button)
            self.buttons.append(button)


class MiniBar(QFrame):
    """Barra do mini player: título, voltar à página do vídeo e fechar. Arrastar a barra move a janela."""

    def __init__(self, tokens):
        super().__init__()
        self.setObjectName("miniBar")
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 4, 6, 4)
        row.setSpacing(4)
        self.title = QLabel()
        self.title.setObjectName("miniTitle")
        self.expand_button = self._button()
        self.close_button = self._button()
        row.addWidget(self.title, 1)
        row.addWidget(self.expand_button)
        row.addWidget(self.close_button)
        self.set_tokens(tokens)

    @staticmethod
    def _button():
        button = QToolButton()
        button.setObjectName("playerButton")
        button.setCursor(Qt.PointingHandCursor)
        button.setFocusPolicy(Qt.TabFocus)
        return button

    def set_tokens(self, tokens):
        self.expand_button.setIcon(icon("maximize", tokens["text_primary"], 16))
        self.close_button.setIcon(icon("close", tokens["text_primary"], 16))

    def mousePressEvent(self, event):
        handle = self.window().windowHandle()
        if event.button() == Qt.LeftButton and handle is not None:
            handle.startSystemMove()
            event.accept()
            return
        super().mousePressEvent(event)


class PlayerWidget(QFrame):
    """Player da tela do vídeo: arquivo local primeiro, YouTube incorporado quando não há arquivo,
    stream direto como alternativa. Salva e retoma a posição."""

    height_changed = Signal(int)  # altura real em reprodução
    source_changed = Signal(str)
    browser_requested = Signal()
    fullscreen_changed = Signal(bool)
    folder_requested = Signal()
    playback_ended = Signal()  # o vídeo terminou (usado na reprodução sequencial de playlists)
    mini_changed = Signal(bool)
    expand_requested = Signal()  # 'voltar à página do vídeo' no mini player

    def __init__(self, translator, tokens, library, progress, settings, local_factory=LocalPlayer, online_factory=create_online_player):
        super().__init__()
        self.setObjectName("playerWidget")
        self._tr = translator
        self._tokens = tokens
        self._library = library
        self._progress = progress
        self._settings = settings
        self._local_factory = local_factory
        self._online_factory = online_factory
        self._local = None
        self._online = None
        self._backend = None
        self._kind = ""
        self._video = None
        self._source_id = None
        self._pos = 0.0
        self._dur = 0.0
        self._muted = False
        self._fullscreen = False
        self._mini = False
        self._cinema = False
        self._host_layout = None
        self._host_index = 0
        self._max_height = None
        self._request = 0
        self.setFocusPolicy(Qt.StrongFocus)

        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        self.mini_bar = MiniBar(tokens)
        self.mini_bar.expand_button.clicked.connect(self.expand_mini)
        self.mini_bar.close_button.clicked.connect(self.close_mini)
        self.mini_bar.hide()
        column.addWidget(self.mini_bar)
        self.stack = QStackedWidget()
        self.stack.setObjectName("playerStack")
        self.blank = QWidget()
        self.message = PlayerMessage()
        self.stack.addWidget(self.blank)
        self.stack.addWidget(self.message)
        column.addWidget(self.stack)

        self.notice = QFrame()
        self.notice.setObjectName("playerNotice")
        notice_row = QHBoxLayout(self.notice)
        notice_row.setContentsMargins(12, 6, 12, 6)
        self.notice_label = QLabel()
        self.restart_button = QPushButton()
        self.restart_button.setObjectName("linkButton")
        self.restart_button.setCursor(Qt.PointingHandCursor)
        self.restart_button.clicked.connect(self.restart)
        notice_row.addWidget(self.notice_label)
        notice_row.addWidget(self.restart_button)
        notice_row.addStretch(1)
        self.notice.hide()
        column.addWidget(self.notice)

        self.controls = PlayerControls(translator, tokens)
        column.addWidget(self.controls)
        c = self.controls
        c.play_toggled.connect(self.toggle_play)
        c.seek_requested.connect(self.seek)
        c.volume_changed.connect(self._on_volume_chosen)
        c.mute_toggled.connect(self.toggle_mute)
        c.rate_selected.connect(lambda rate: self._backend and self._backend.set_rate(rate))
        c.quality_selected.connect(lambda height: self._backend and self._backend.set_quality(height))
        c.fullscreen_toggled.connect(self.toggle_fullscreen)
        c.mini_toggled.connect(self.toggle_mini)

        self._save_timer = QTimer(self)
        self._save_timer.setInterval(SAVE_INTERVAL_MS)
        self._save_timer.timeout.connect(self.save_progress)
        self._notice_timer = QTimer(self)
        self._notice_timer.setSingleShot(True)
        self._notice_timer.setInterval(NOTICE_MS)
        self._notice_timer.timeout.connect(self.notice.hide)
        self.setMaximumWidth(self._width_limit())
        self.retranslate()

    # ------------------------------------------------------------------------------------
    # abertura
    # ------------------------------------------------------------------------------------
    @property
    def kind(self):
        return self._kind

    @property
    def video(self):
        return self._video

    def _width_limit(self):
        return UNLIMITED if self._cinema else MAX_WIDTH

    def set_cinema(self, enabled):
        """Modo cinema: sem limite de largura (o limite passa a ser a altura disponível)."""
        if enabled != self._cinema:
            self._cinema = enabled
            if not self._mini and not self._fullscreen:
                self.setMaximumWidth(self._width_limit())
            if self._max_height:
                self.set_max_height(self._max_height)

    def set_compact(self, compact):
        self.controls.set_compact(compact)

    def is_playing(self):
        return self._backend is not None and self._backend.is_playing()

    @property
    def position(self):
        """Posição atual em segundos."""
        return self._pos

    def is_idle(self):
        """True quando não há nada carregado nem mensagem na tela (ex.: logo após `stop()`)."""
        return self._backend is None and self.stack.currentWidget() is self.blank

    def open(self, source_id, video=None):
        """Abre um vídeo: arquivo local verificado primeiro; senão o player online."""
        self.stop()
        self._request += 1
        self._source_id, self._video = source_id, video
        self._update_mini_title()
        self._pos = self._dur = 0.0
        self.controls.reset()
        start = self._resume_start()
        path = self._library.local_path(video) if video is not None and self._library.ready else None
        if path is not None:
            self._start_local(path, start)
        else:
            self._start_online(start)

    def attach_video(self, video):
        """Associa (ou desassocia) o registro da biblioteca sem reiniciar a reprodução, para salvar o progresso."""
        self._video = video
        self._update_mini_title()

    def _resume_start(self):
        self.notice.hide()
        video = self._video
        if video is None or not self._library.ready or not self._settings.resume_enabled:
            return 0.0
        start = self._progress.resume_position(video.id, video.duration)
        if start > 0:
            self.notice_label.setText(self._tr.t("player.resume_notice", time=format_duration(start)))
            self.notice.show()
            self._notice_timer.start()
        return start

    def _get_local(self):
        if self._local is None:
            self._local = self._local_factory()
            self._wire(self._local)
            self.stack.addWidget(self._local)
        return self._local

    def _get_online(self):
        if self._online is None:
            backend = self._online_factory()
            if backend is None:
                return None
            self._online = backend
            self._wire(backend)
            self.stack.addWidget(backend)
        return self._online

    def _wire(self, backend):
        backend.loaded.connect(lambda b=backend: self._on_loaded(b))
        backend.state_changed.connect(lambda playing, b=backend: self._on_state(b, playing))
        backend.position_changed.connect(lambda p, d, b=backend: self._on_position(b, p, d))
        backend.quality_changed.connect(lambda h, hs, b=backend: self._on_quality(b, h, hs))
        backend.status_changed.connect(lambda v, m, r, b=backend: self._on_status(b, v, m, r))
        backend.error.connect(lambda code, detail, b=backend: self._on_error(b, code, detail))
        backend.ended.connect(lambda b=backend: self._on_ended(b))
        backend.clicked.connect(lambda b=backend: b is self._backend and self.toggle_play())

    def _activate(self, backend, kind):
        for other in (self._local, self._online):
            if other is not None and other is not backend:
                other.pause()
        self._backend, self._kind = backend, kind
        self.stack.setCurrentWidget(backend)
        self.controls.set_source(kind)
        self.controls.set_quality(0, [], backend.can_change_quality())
        self.source_changed.emit(kind)

    def _start_local(self, path, start, kind=SOURCE_LOCAL):
        local = self._get_local()
        self._activate(local, kind)
        local.load_file(path, start)

    def _start_online(self, start=0.0):
        online = self._get_online()
        if online is None:
            self._backend, self._kind = None, ""
            self._show_message(self._tr.t("player.no_webengine"), [self._browser_action()])
            return
        self._activate(online, SOURCE_ONLINE)
        online.load(self._source_id, start)

    def _start_stream(self):
        """'Player próprio': resolve a URL direta pelos provedores e toca no player local."""
        self._request += 1
        token, source_id, start = self._request, self._source_id, self._pos
        self._show_message(self._tr.t("player.loading_stream"), [])
        run_async(
            lambda: self._library.stream_url(source_id),
            lambda result: self._on_stream_ready(token, result, start),
            lambda exc: self._on_stream_failed(token, exc),
        )

    def _on_stream_ready(self, token, result, start):
        if token != self._request:
            return
        url, _height = result
        local = self._get_local()
        self._activate(local, SOURCE_STREAM)
        local.load_url(url, start)

    def _on_stream_failed(self, token, exc):
        if token != self._request:
            return
        code = getattr(exc, "code", "failed")
        text = f"{self._tr.t('player.stream_failed')} {describe_error(self._tr, code)}"
        self._show_message(text, [self._browser_action()])

    # ------------------------------------------------------------------------------------
    # mensagens e erros
    # ------------------------------------------------------------------------------------
    def _browser_action(self):
        return (self._tr.t("watch.open_browser"), self.browser_requested.emit)

    def _show_message(self, text, actions):
        self.message.show_message(text, actions)
        self.stack.setCurrentWidget(self.message)

    def _on_error(self, backend, code, detail):
        if backend is not self._backend:
            return
        t = self._tr.t
        browser = self._browser_action()
        retry = (t("watch.retry"), self._retry)
        if self._kind == SOURCE_LOCAL:
            actions = [retry, (t("player.watch_online"), lambda: self._start_online(self._pos)), (t("card.menu_folder"), self.folder_requested.emit)]
            text = t("player.local_failed")
        elif self._kind == SOURCE_ONLINE:
            own = (t("player.use_own"), self._start_stream)
            if code == "embed_blocked":
                text, actions = t("player.embed_blocked"), [own, browser]
            elif code == "unavailable":
                text, actions = t("player.unavailable"), [browser]
            elif code == "network":
                text, actions = t("player.network"), [retry, own, browser]
            else:
                text, actions = t("player.failed"), [retry, own, browser]
        else:
            text, actions = t("player.stream_failed"), [browser]
        backend.pause()
        self._show_message(text, actions)

    def _retry(self):
        if self._source_id:
            self.open(self._source_id, self._video)

    # ------------------------------------------------------------------------------------
    # eventos do motor atual
    # ------------------------------------------------------------------------------------
    def _on_loaded(self, backend):
        if backend is not self._backend:
            return
        backend.set_volume(self._settings.player_volume)
        if self._settings.default_rate != 1.0:
            backend.set_rate(self._settings.default_rate)
        self.stack.setCurrentWidget(backend)

    def _on_state(self, backend, playing):
        if backend is not self._backend:
            return
        self.controls.set_playing(playing)
        if playing:
            self._save_timer.start()
        else:
            self._save_timer.stop()
            self.save_progress()

    def _on_position(self, backend, position, duration):
        if backend is not self._backend:
            return
        self._pos, self._dur = position, duration
        self.controls.set_position(position, duration)

    def _on_quality(self, backend, height, available):
        if backend is not self._backend:
            return
        self.controls.set_quality(height, available, backend.can_change_quality())
        if height:
            self.height_changed.emit(height)

    def _on_status(self, backend, volume, muted, rate):
        if backend is not self._backend:
            return
        self._muted = muted
        self.controls.set_status(volume, muted, rate)

    def _on_ended(self, backend):
        if backend is not self._backend:
            return
        self.controls.set_playing(False)
        self._save_timer.stop()
        if self._dur > 0:
            self._pos = self._dur
            self.save_progress()
        self.playback_ended.emit()

    # ------------------------------------------------------------------------------------
    # comandos
    # ------------------------------------------------------------------------------------
    def toggle_play(self):
        if self._backend is None:
            return
        self._backend.toggle()

    def seek(self, seconds):
        if self._backend is None:
            return
        self._backend.seek(playback.clamp_seek(seconds, self._dur))

    def seek_by(self, delta):
        self.seek(self._pos + delta)

    def _on_volume_chosen(self, percent):
        self._settings.player_volume = int(percent)
        if self._backend is not None:
            self._backend.set_volume(percent)
            if percent > 0 and self._muted:
                self._backend.set_muted(False)

    def set_volume(self, percent):
        percent = max(0, min(100, int(percent)))
        self.controls.volume_slider.setValue(percent)  # dispara _on_volume_chosen

    def toggle_mute(self):
        if self._backend is not None:
            self._backend.set_muted(not self._muted)

    def restart(self):
        """'Recomeçar do início': esquece a posição salva e volta ao começo."""
        self.notice.hide()
        if self._video is not None and self._library.ready:
            self._progress.restart(self._video.id)
        self.seek(0)

    def save_progress(self):
        if self._video is None or self._video.id is None or not self._library.ready:
            return
        if self._dur > 0 and (self._pos > 0 or self._backend is not None and not self._backend.is_playing()):
            self._progress.save(self._video.id, self._pos, self._dur)

    def stop(self):
        """Para a reprodução e grava a posição. Depois zera a posição em memória: um novo stop() ou open() não pode
        regravar um valor velho por cima de um progresso mais novo."""
        self.save_progress()
        self._request += 1  # respostas atrasadas (stream, etc.) não podem religar o vídeo depois da parada
        self._pos = self._dur = 0.0
        self._save_timer.stop()
        self._notice_timer.stop()
        self.notice.hide()
        for backend in (self._local, self._online):
            if backend is not None:
                backend.stop()
        self._backend, self._kind = None, ""
        self.controls.reset()
        self.stack.setCurrentWidget(self.blank)

    def shutdown(self):
        self.stop()
        if self._fullscreen:
            self.exit_fullscreen()
        if self._mini:
            self.exit_mini()
        if self._online is not None:
            self._online.shutdown()
            self._online = None

    # ------------------------------------------------------------------------------------
    # atalhos
    # ------------------------------------------------------------------------------------
    def perform(self, action):
        if action == shortcuts.PLAY_PAUSE:
            self.toggle_play()
        elif action in (shortcuts.SEEK_BACK, shortcuts.SEEK_FORWARD):
            self.seek_by(shortcuts.seek_delta(action))
        elif action in (shortcuts.VOLUME_UP, shortcuts.VOLUME_DOWN):
            self.set_volume(self.controls.volume_slider.value() + shortcuts.volume_delta(action))
        elif action == shortcuts.MUTE:
            self.toggle_mute()
        elif action == shortcuts.FULLSCREEN:
            self.toggle_fullscreen()
        elif action == shortcuts.EXIT_FULLSCREEN:
            self.exit_fullscreen()
        elif action == shortcuts.MINI:
            self.toggle_mini()

    def keyPressEvent(self, event):
        action = shortcuts.action_for(event.key(), event.modifiers())
        if action is not None and (self._fullscreen or action != shortcuts.EXIT_FULLSCREEN):
            if not shortcuts.should_ignore(QApplication.focusWidget(), action):
                self.perform(action)
                event.accept()
                return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------------------------
    # tela cheia e geometria
    # ------------------------------------------------------------------------------------
    @property
    def is_fullscreen(self):
        return self._fullscreen

    def toggle_fullscreen(self):
        self.exit_fullscreen() if self._fullscreen else self.enter_fullscreen()

    def enter_fullscreen(self):
        parent = self.parentWidget()
        if self._mini:
            self.expand_mini()
            parent = self.parentWidget()
        if self._fullscreen or parent is None or parent.layout() is None:
            return
        self._host_layout = parent.layout()
        self._host_index = self._host_layout.indexOf(self)
        self._host_layout.removeWidget(self)
        self._fullscreen = True
        self.setMaximumWidth(16777215)
        self.setParent(None)
        self.setWindowFlag(Qt.Window, True)
        self.showFullScreen()
        self.setFocus()
        self._after_fullscreen_change()

    def exit_fullscreen(self):
        if not self._fullscreen:
            return
        self._fullscreen = False
        self.showNormal()
        self.setWindowFlag(Qt.Window, False)
        self.setMaximumWidth(self._width_limit())
        if self._host_layout is not None:
            self._host_layout.insertWidget(self._host_index, self)
        self.show()
        self._after_fullscreen_change()

    def _after_fullscreen_change(self):
        self.controls.set_fullscreen(self._fullscreen)
        self._apply_geometry()
        self.fullscreen_changed.emit(self._fullscreen)

    # ------------------------------------------------------------------------------------
    # mini player: o mesmo player numa janelinha flutuante, sempre por cima das outras
    # ------------------------------------------------------------------------------------
    @property
    def is_mini(self):
        return self._mini

    def toggle_mini(self):
        self.expand_mini() if self._mini else self.enter_mini()

    def enter_mini(self):
        parent = self.parentWidget()
        if self._mini or self._fullscreen or self._backend is None or parent is None or parent.layout() is None:
            return
        self._host_layout = parent.layout()
        self._host_index = self._host_layout.indexOf(self)
        self._host_layout.removeWidget(self)
        self._mini = True
        self.notice.hide()
        self.setParent(None)
        self.setWindowFlags(Qt.Window | Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(MINI_WIDTH)
        self.setMaximumWidth(MINI_WIDTH)
        self.mini_bar.show()
        self.controls.set_mini(True)
        self._update_mini_title()
        self._apply_geometry()
        self.adjustSize()
        self._place_mini()
        self.show()
        self.setFocus()
        self.mini_changed.emit(True)

    def _place_mini(self):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.move(area.right() - self.width() - MINI_MARGIN, area.bottom() - self.height() - MINI_MARGIN)

    def exit_mini(self):
        """Devolve o player à página do vídeo, sem mexer na reprodução."""
        if not self._mini:
            return
        self._mini = False
        self.hide()
        self.setWindowFlags(Qt.Widget)
        self.setMinimumWidth(0)
        self.setMaximumWidth(self._width_limit())
        self.mini_bar.hide()
        self.controls.set_mini(False)
        if self._host_layout is not None:
            self._host_layout.insertWidget(self._host_index, self)
        self.show()
        self._apply_geometry()
        self.mini_changed.emit(False)

    def expand_mini(self):
        if self._mini:
            self.exit_mini()
            self.expand_requested.emit()

    def close_mini(self):
        """'X' do mini player: volta ao lugar de origem e para o vídeo (gravando a posição)."""
        if self._mini:
            self.exit_mini()
            self.stop()

    def _update_mini_title(self):
        title = self._video.title if self._video is not None else ""
        self.mini_bar.title.setText(title)
        self.mini_bar.title.setToolTip(title)

    def set_max_height(self, height):
        self._max_height = max(220, int(height))
        controls_h = self.controls.sizeHint().height()
        self.setMaximumWidth(min(self._width_limit(), int((self._max_height - controls_h) * 16 / 9)))
        self._apply_geometry()

    def _apply_geometry(self):
        if self._mini:
            self.stack.setFixedHeight(int(self.width() * 9 / 16))
            return
        if self._fullscreen:
            self.stack.setMinimumHeight(0)
            self.stack.setMaximumHeight(16777215)
            return
        controls_h = self.controls.sizeHint().height() + (self.notice.sizeHint().height() if self.notice.isVisible() else 0)
        height = int(self.width() * 9 / 16)
        if self._max_height:
            height = min(height, max(120, self._max_height - controls_h))
        self.stack.setFixedHeight(max(120, height))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_geometry()

    # ------------------------------------------------------------------------------------
    # tema e idioma
    # ------------------------------------------------------------------------------------
    def set_tokens(self, tokens):
        self._tokens = tokens
        self.controls.set_tokens(tokens)
        self.mini_bar.set_tokens(tokens)

    def retranslate(self):
        self.controls.retranslate()
        self.mini_bar.expand_button.setToolTip(self._tr.t("player.mini_expand"))
        self.mini_bar.expand_button.setAccessibleName(self._tr.t("player.mini_expand"))
        self.mini_bar.close_button.setToolTip(self._tr.t("player.mini_close"))
        self.mini_bar.close_button.setAccessibleName(self._tr.t("player.mini_close"))
        self.restart_button.setText(self._tr.t("player.restart"))
