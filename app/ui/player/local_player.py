from PySide6.QtCore import QEvent, Qt, QUrl, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaMetaData, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QVBoxLayout

from app.ui.player.base import PlayerBackend


class LocalPlayer(PlayerBackend):
    """Reproduz um arquivo local (ou um stream direto) com o QtMultimedia."""

    def __init__(self):
        super().__init__()
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)
        self._video = QVideoWidget(self)
        self._video.setStyleSheet("background: #000000;")
        self._player.setVideoOutput(self._video)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._video)
        self._video.installEventFilter(self)

        self._start = 0.0
        self._autoplay = True
        self._height = 0
        # Ligações a métodos @Slot, sempre em fila (QueuedConnection):
        #  - lambdas rodariam na thread de decodificação e podem travar ao disputar o GIL;
        #  - QMediaPlayer.stop() emite os sinais de forma síncrona, ainda no meio da parada. Mexer em menus e widgets ali
        #    dentro trava o aplicativo. Em fila, o nosso código só roda depois que a chamada retorna.
        queued = Qt.QueuedConnection
        self._player.playbackStateChanged.connect(self._on_state, queued)
        self._player.positionChanged.connect(self._on_position, queued)
        self._player.durationChanged.connect(self._on_duration, queued)
        self._player.metaDataChanged.connect(self._on_metadata, queued)
        self._player.mediaStatusChanged.connect(self._on_status, queued)
        self._player.errorOccurred.connect(self._on_error, queued)
        self._audio.volumeChanged.connect(self._emit_status, queued)
        self._audio.mutedChanged.connect(self._emit_status, queued)
        self._player.playbackRateChanged.connect(self._emit_status, queued)

    @Slot(QMediaPlayer.PlaybackState)
    def _on_state(self, state):
        self.state_changed.emit(state == QMediaPlayer.PlayingState)

    @Slot("qlonglong")
    def _on_position(self, ms):
        self.position_changed.emit(ms / 1000, self._player.duration() / 1000)

    @Slot("qlonglong")
    def _on_duration(self, ms):
        self.position_changed.emit(self._player.position() / 1000, ms / 1000)

    @Slot(QMediaPlayer.Error, str)
    def _on_error(self, _error, text):
        self.error.emit("local_failed", text)

    # -- carga ---------------------------------------------------------------------
    def load_file(self, path, start=0.0, autoplay=True):
        self._load(QUrl.fromLocalFile(str(path)), start, autoplay)

    def load_url(self, url, start=0.0, autoplay=True):
        self._load(QUrl(url), start, autoplay)

    def _load(self, url, start, autoplay):
        self._start, self._autoplay, self._height = max(0.0, start), autoplay, 0
        self._player.setSource(url)

    @Slot(QMediaPlayer.MediaStatus)
    def _on_status(self, status):
        if status == QMediaPlayer.LoadedMedia:
            if self._start > 0:
                self._player.setPosition(int(self._start * 1000))
                self._start = 0.0
            self.loaded.emit()
            if self._autoplay:
                self._player.play()
                self._autoplay = False
        elif status == QMediaPlayer.EndOfMedia:
            self.ended.emit()
        elif status == QMediaPlayer.InvalidMedia:
            self.error.emit("local_failed", "mídia inválida ou formato sem suporte")

    @Slot()
    def _on_metadata(self):
        size = self._player.metaData().value(QMediaMetaData.Resolution)
        height = int(size.height()) if size is not None and hasattr(size, "height") else 0
        if height and height != self._height:
            self._height = height
            self.quality_changed.emit(height, [height])

    @Slot()
    @Slot(float)
    @Slot(bool)
    def _emit_status(self, *_args):
        self.status_changed.emit(int(round(self._audio.volume() * 100)), self._audio.isMuted(), self._player.playbackRate())

    # -- comandos -------------------------------------------------------------------
    def play(self):
        self._player.play()

    def pause(self):
        self._player.pause()

    def stop(self):
        self._autoplay, self._start = False, 0.0  # um 'carregou' que chegue depois não pode tocar nada
        self._player.stop()
        self._player.setSource(QUrl())

    def seek(self, seconds):
        self._player.setPosition(max(0, int(seconds * 1000)))

    def set_volume(self, percent):
        self._audio.setVolume(max(0, min(100, percent)) / 100)

    def set_muted(self, muted):
        self._audio.setMuted(bool(muted))

    def set_rate(self, rate):
        self._player.setPlaybackRate(rate)

    def position(self):
        return self._player.position() / 1000

    def duration(self):
        return self._player.duration() / 1000

    def is_playing(self):
        return self._player.playbackState() == QMediaPlayer.PlayingState

    def current_height(self):
        return self._height

    def eventFilter(self, obj, event):
        if obj is self._video and event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            self.clicked.emit()
        return super().eventFilter(obj, event)
