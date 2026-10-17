from urllib.parse import urlparse

from PySide6.QtCore import QCoreApplication, QEvent, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout

from app.domain import playback
from app.infrastructure.media import embed
from app.ui.player.base import PlayerBackend

# Hosts que o iframe do player precisa contatar. Nada fora disso é carregado em subquadros.
_ALLOWED_HOST_SUFFIXES = ("youtube.com", "youtube-nocookie.com", "ytimg.com", "googlevideo.com", "google.com", "gstatic.com", "googleapis.com", "ggpht.com")
LOAD_TIMEOUT_MS = 20000


def host_allowed(url):
    host = (urlparse(url).hostname or "").lower()
    return any(host == s or host.endswith("." + s) for s in _ALLOWED_HOST_SUFFIXES)


class EmbedPage(QWebEnginePage):
    """Página isolada: só carrega o nosso HTML e os hosts do player; bloqueia navegação e pop-ups."""

    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.allow_main_load = False

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if is_main_frame:
            allowed = self.allow_main_load
            self.allow_main_load = False
            return allowed
        return host_allowed(url.toString()) or url.scheme() in ("about", "blob", "data")

    def createWindow(self, _window_type):
        return None  # sem pop-ups ("Assistir no YouTube" etc.)


class OnlinePlayer(PlayerBackend):
    """Reproduz o vídeo pelo player incorporado do YouTube, controlado pelos nossos botões."""

    def __init__(self, api_script=None, timeout_ms=LOAD_TIMEOUT_MS):
        super().__init__()
        self._api_script = api_script
        self._position = 0.0
        self._duration = 0.0
        self._playing = False
        self._levels = []
        self._height = 0
        self._ready = False

        self._profile = QWebEngineProfile()  # sem nome = perfil temporário: nenhum cookie fica gravado
        self._page = EmbedPage(self._profile, self)
        self._profile.setParent(self._page)  # o perfil precisa ser destruído DEPOIS da página
        settings = self._page.settings()
        settings.setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture, False)
        settings.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, False)
        settings.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, False)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, False)
        settings.setAttribute(QWebEngineSettings.ErrorPageEnabled, False)

        self._bridge = embed.EmbedBridge(self)
        self._channel = QWebChannel(self)
        self._channel.registerObject("bridge", self._bridge)
        self._page.setWebChannel(self._channel)

        self._view = QWebEngineView(self)
        self._view.setPage(self._page)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(timeout_ms)
        self._timer.timeout.connect(lambda: self.error.emit("network", "o player do YouTube não respondeu"))

        b = self._bridge
        b.ready.connect(self._on_ready)
        b.state_changed.connect(self._on_state)
        b.time_changed.connect(self._on_time)
        b.quality_changed.connect(self._on_quality)
        b.status_changed.connect(lambda v, m, r: self.status_changed.emit(int(round(v)), m, r))
        b.error.connect(lambda code, yt: (self._timer.stop(), self.error.emit(code, f"youtube:{yt}")))

    # -- carga -----------------------------------------------------------------------
    def load(self, video_id, start=0.0):
        self._ready, self._height, self._levels, self._position, self._duration = False, 0, [], 0.0, 0.0
        html = embed.build_html(video_id, int(start), self._api_script, embed.webchannel_source())
        self._page.allow_main_load = True
        self._page.setHtml(html, QUrl(embed.ORIGIN + "/"))
        self._timer.start()

    def _on_ready(self):
        self._ready = True
        self._timer.stop()
        self.loaded.emit()

    def _on_state(self, state):
        playing = state == embed.STATE_PLAYING
        if playing != self._playing:
            self._playing = playing
            self.state_changed.emit(playing)
        if state == embed.STATE_ENDED:
            self.ended.emit()

    def _on_time(self, position, duration):
        self._position, self._duration = position, duration
        self.position_changed.emit(position, duration)

    def _on_quality(self, level, levels):
        if levels:
            self._levels = playback.available_heights(levels)
        height = playback.height_from_level(level) or 0
        if height:
            self._height = height
        self.quality_changed.emit(self._height, list(self._levels))

    # -- comandos ----------------------------------------------------------------------
    def _js(self, command):
        self._page.runJavaScript(f"window.dino && window.dino.{command}")

    def play(self):
        self._js("play()")

    def pause(self):
        self._js("pause()")

    def stop(self):
        self._timer.stop()
        self._ready = False
        self._playing = False
        self._page.setHtml("", QUrl("about:blank"))

    def seek(self, seconds):
        self._position = max(0.0, seconds)
        self._js(f"seek({self._position})")

    def set_volume(self, percent):
        self._js(f"volume({int(max(0, min(100, percent)))})")

    def set_muted(self, muted):
        self._js(f"mute({'true' if muted else 'false'})")

    def set_rate(self, rate):
        self._js(f"rate({float(rate)})")

    def set_quality(self, height):
        self._js(f"quality('{playback.level_from_height(height) if height else 'default'}')")

    def can_change_quality(self):
        return True

    def position(self):
        return self._position

    def duration(self):
        return self._duration

    def is_playing(self):
        return self._playing

    def current_height(self):
        return self._height

    def shutdown(self):
        """Encerramento ordenado: a view e a página saem antes do perfil. Sem isso o Chromium pode travar ao sair."""
        self._timer.stop()
        self._ready = self._playing = False
        view, page = self._view, self._page
        view.setParent(None)
        view.deleteLater()
        page.deleteLater()  # o perfil é filho da página e sai depois dela
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def run_script(self, script, callback=None):
        """Executa JavaScript na página (uso de testes e diagnóstico)."""
        if callback is None:
            self._page.runJavaScript(script)
        else:
            self._page.runJavaScript(script, callback)
