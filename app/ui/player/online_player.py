from urllib.parse import urlparse

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QRect, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QPalette
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.domain import playback
from app.infrastructure.media import embed
from app.ui.player.base import PlayerBackend

# Hosts que o iframe do player precisa contatar. Nada fora disso é carregado em subquadros.
_ALLOWED_HOST_SUFFIXES = ("youtube.com", "youtube-nocookie.com", "ytimg.com", "googlevideo.com", "google.com", "gstatic.com", "googleapis.com", "ggpht.com")
LOAD_TIMEOUT_MS = 20000
AUTO_HEIGHT = 1080  # o YouTube escolhe a qualidade pelo tamanho do player: "automático" aqui significa até Full HD
MIN_ZOOM, MAX_ZOOM = 0.25, 5.0
# O YouTube hoje costuma devolver uma lista vazia de qualidades (e ignora setPlaybackQuality): oferecemos estas e
# controlamos a qualidade pelo tamanho virtual da página (zoom), que é o que o player realmente respeita.
DEFAULT_HEIGHTS = (1080, 720, 480, 360, 240, 144)
RETRY_MS = 8000  # sem resposta do player nesse tempo: recarrega sozinho (até MAX_RETRIES vezes) antes de mostrar erro
MAX_RETRIES = 2
QUALITY_CHECK_MS = 3500  # depois de pedir uma qualidade, confere se o YouTube obedeceu; se não, recarrega naquele ponto


def host_allowed(url):
    host = (urlparse(url).hostname or "").lower()
    return any(host == s or host.endswith("." + s) for s in _ALLOWED_HOST_SUFFIXES)


class EmbedPage(QWebEnginePage):
    """Página isolada: só carrega o nosso HTML e os hosts do player; bloqueia navegação e pop-ups."""

    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.allowed_loads = 0  # quantas cargas nossas (setHtml) ainda não chegaram; um contador evita perder uma delas

    def allow_next_load(self):
        self.allowed_loads += 1

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if is_main_frame:
            if self.allowed_loads > 0:
                self.allowed_loads -= 1
                return True
            return False
        return host_allowed(url.toString()) or url.scheme() in ("about", "blob", "data")

    def createWindow(self, _window_type):
        return None  # sem pop-ups ("Assistir no YouTube" etc.)


OVERLAY_FLAGS = Qt.Tool | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
OVERLAY_TICK_MS = 40


class VideoOverlay(QWidget):
    """Janela opaca, sem moldura e "filha" da janela principal, que hospeda a imagem do Chromium.

    O Chromium (QtWebEngine) não convive bem com uma janela de transparência por pixel: o Qt troca a forma de desenhar
    a janela inteira quando a imagem aparece, e o efeito de vidro se perde (a janela fica cinza e opaca). Com o vídeo
    numa janela própria por cima do espaço do player, a janela de vidro nunca contém o Chromium e fica estável."""

    def __init__(self, owner):
        super().__init__(owner, OVERLAY_FLAGS)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.Window, Qt.black)
        self.setPalette(palette)


class OnlinePlayer(PlayerBackend):
    """Reproduz o vídeo pelo player incorporado do YouTube, controlado pelos nossos botões."""

    def __init__(self, api_script=None, timeout_ms=LOAD_TIMEOUT_MS):
        super().__init__()
        self._api_script = api_script
        self._position = 0.0
        self._duration = 0.0
        self._playing = False
        self._levels = list(DEFAULT_HEIGHTS)
        self._height = 0
        self._ready = False
        self._target_height = AUTO_HEIGHT
        self._video_id, self._start, self._retries = None, 0.0, 0
        self._wanted_height = None  # qualidade pedida pelo usuário, ainda a confirmar

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
        self._view.installEventFilter(self)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self._view)
        self._overlay = None  # janela que hospeda a view quando a janela principal é translúcida (Vidro cinza)
        self._overlay_owner = None
        self._overlay_timer = QTimer(self)
        self._overlay_timer.setInterval(OVERLAY_TICK_MS)
        self._overlay_timer.timeout.connect(self._sync_overlay)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timeout_ms = timeout_ms
        self._timer.setInterval(min(RETRY_MS, timeout_ms))
        self._timer.timeout.connect(self._on_load_timeout)
        self._quality_timer = QTimer(self)
        self._quality_timer.setSingleShot(True)
        self._quality_timer.setInterval(QUALITY_CHECK_MS)
        self._quality_timer.timeout.connect(self._check_quality)

        b = self._bridge
        b.ready.connect(self._on_ready)
        b.state_changed.connect(self._on_state)
        b.time_changed.connect(self._on_time)
        b.quality_changed.connect(self._on_quality)
        b.status_changed.connect(lambda v, m, r: self.status_changed.emit(int(round(v)), m, r))
        b.error.connect(lambda code, yt: (self._timer.stop(), self.error.emit(code, f"youtube:{yt}")))

    # -- carga -----------------------------------------------------------------------
    # -- qualidade: o YouTube decide pelo tamanho (em px CSS) do player, não só pela banda ------------
    @staticmethod
    def css_width_for(height):
        return max(256, int(round(height * 16 / 9)))

    def zoom_for(self, width):
        """Zoom da página que faz o player enxergar uma área de `target_height` de altura, mesmo numa janela pequena.
        Com o zoom a página tem mais pixels CSS que pixels reais; é isso que faz o YouTube oferecer HD."""
        if width <= 0:
            return 1.0
        return max(MIN_ZOOM, min(MAX_ZOOM, width / self.css_width_for(self._target_height)))

    def _apply_zoom(self):
        zoom = self.zoom_for(self._view.width())
        if abs(zoom - self._view.zoomFactor()) > 0.005:
            self._view.setZoomFactor(zoom)

    @property
    def target_height(self):
        return self._target_height

    def eventFilter(self, obj, event):
        kind = event.type()
        if obj is self._view and kind == QEvent.Resize:
            self._apply_zoom()
        elif self._overlay is not None and obj is not self._view and kind in (
                QEvent.Move, QEvent.Resize, QEvent.Show, QEvent.Hide, QEvent.WindowStateChange, QEvent.WinIdChange):
            self._sync_overlay()
        return super().eventFilter(obj, event)

    def load(self, video_id, start=0.0):
        self._video_id, self._start, self._retries = video_id, start, 0
        self._ready, self._height, self._levels, self._position, self._duration = False, 0, list(DEFAULT_HEIGHTS), 0.0, 0.0
        self._start_page(video_id, start)

    def _start_page(self, video_id, start):
        self._apply_zoom()
        html = embed.build_html(video_id, int(start), self._api_script, embed.webchannel_source())
        self._page.allow_next_load()
        self._page.setHtml(html, QUrl(embed.ORIGIN + "/"))
        self._timer.start()

    def _on_load_timeout(self):
        """O player não respondeu: costuma ser a API do YouTube que não chegou (tela preta). Tenta de novo antes de desistir."""
        if self._video_id is None or self._ready:
            return
        if self._retries < MAX_RETRIES and self._timeout_ms > RETRY_MS:
            self._retries += 1
            self._start_page(self._video_id, self._position or self._start)
            return
        self.error.emit("network", "o player do YouTube não respondeu")

    def _on_ready(self):
        self._ready = True
        self._timer.stop()
        self.loaded.emit()
        QTimer.singleShot(250, self._nudge)

    # -- hospedagem da imagem: embutida, ou numa janela própria sobre uma janela translúcida -------------------
    def _wants_overlay(self):
        window = self.window()
        return window is not self and window.testAttribute(Qt.WA_TranslucentBackground)

    def sync_host(self):
        """Decide onde a imagem do Chromium mora: no próprio widget, ou na janela de sobreposição quando a janela
        principal tem transparência por pixel. Chamado ao mostrar, ao trocar de tema e ao recriar a janela."""
        if self._view is None:
            return
        wanted = self._wants_overlay()
        if wanted and (self._overlay is None or self._overlay_owner is not self.window()):
            self._attach_overlay()
        elif not wanted and self._overlay is not None:
            self._detach_overlay()
        self._sync_overlay()

    def _attach_overlay(self):
        owner = self.window()
        if self._overlay is not None:
            self._release_overlay_owner()
            self._overlay.setParent(owner, OVERLAY_FLAGS)
        else:
            self._overlay = VideoOverlay(owner)
            self._layout.removeWidget(self._view)
            self._view.setParent(self._overlay)
        self._overlay_owner = owner
        owner.installEventFilter(self)
        self.installEventFilter(self)
        self._overlay_timer.start()

    def _release_overlay_owner(self):
        if self._overlay_owner is not None:
            try:
                self._overlay_owner.removeEventFilter(self)
            except RuntimeError:  # a janela dona já foi destruída
                pass
        self._overlay_owner = None

    def _detach_overlay(self):
        self._overlay_timer.stop()
        self._release_overlay_owner()
        overlay, self._overlay = self._overlay, None
        if overlay is not None:
            overlay.hide()
            self._view.setParent(self)
            self._view.setGeometry(self.rect())
            self._layout.addWidget(self._view)
            self._view.show()
            overlay.deleteLater()

    def _sync_overlay(self):
        """Põe a janela de sobreposição exatamente sobre a parte visível do player (recortada por barras de rolagem,
        painéis por cima etc.) e a esconde quando o player não está à vista."""
        overlay = self._overlay
        if overlay is None:
            return
        window = self.window()
        visible = self.isVisible() and window.isVisible() and not window.isMinimized()
        region = self.visibleRegion() if visible else None
        bounds = region.boundingRect() if region is not None else QRect()
        if bounds.isEmpty():
            if overlay.isVisible():
                overlay.hide()
            return
        target = QRect(self.mapToGlobal(bounds.topLeft()), bounds.size())
        if overlay.geometry() != target:
            overlay.setGeometry(target)
        view_geometry = QRect(QPoint(-bounds.x(), -bounds.y()), self.size())
        if self._view.geometry() != view_geometry:
            self._view.setGeometry(view_geometry)
        if region.rectCount() > 1:  # algo (ex.: a barra do modo cinema) cobre parte do vídeo: a janela é recortada
            overlay.setMask(region.translated(-bounds.topLeft()))
        elif overlay.mask().boundingRect() != QRect():
            overlay.clearMask()
        if not overlay.isVisible():
            overlay.show()

    def showEvent(self, event):
        super().showEvent(event)
        self.sync_host()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._sync_overlay()  # o vídeo some junto com a página, sem esperar o próximo ciclo

    def refresh_surface(self):
        """A janela do sistema foi recriada (ex.: Vidro cinza): o Chromium precisa reanexar a superfície da imagem,
        senão o vídeo some e só o áudio continua. Esconder e mostrar a view faz isso sem recarregar o vídeo."""
        self.sync_host()
        if self._view is None or not self._view.isVisible():
            return
        self._view.hide()
        self._view.show()
        QTimer.singleShot(150, self._nudge)

    def _nudge(self):
        """Força a repintura: em alguns sistemas a view do Chromium fica preta até a página mudar de tamanho."""
        if self._view is None:
            return
        zoom = self._view.zoomFactor()
        self._view.setZoomFactor(zoom + 0.001)
        self._view.setZoomFactor(zoom)
        self._view.update()

    def _on_state(self, state):
        playing = state in (embed.STATE_PLAYING, embed.STATE_BUFFERING)  # carregando trecho = ainda quer tocar
        if playing != self._playing:
            self._playing = playing
            self.state_changed.emit(playing)
        if state == embed.STATE_ENDED:
            self.ended.emit()

    def _on_time(self, position, duration):
        self._position, self._duration = position, duration
        self.position_changed.emit(position, duration)

    def _on_quality(self, level, levels):
        reported = playback.available_heights(levels)
        if len(reported) > 1:  # uma lista de 0 ou 1 nível não ajuda o usuário a escolher: mantém a padrão
            self._levels = reported
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

    def toggle(self):
        """Decide dentro da página, com o estado de agora: o último que recebemos pode estar até meio segundo atrasado
        (ou o usuário acabou de clicar no vídeo), e aí o botão fazia o contrário do esperado."""
        self._js("toggle()")

    def stop(self):
        """Para de verdade: troca a página por uma em branco (o iframe do YouTube é destruído e o som cala).
        Só pausar não basta: se o player ainda carrega, o autoplay dele liga o vídeo depois, sem ninguém assistindo."""
        self._timer.stop()
        self._quality_timer.stop()
        self._ready = False
        self._playing = False
        self._video_id = None
        self._page.allow_next_load()  # sem isso a navegação para a página em branco seria recusada
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
        """O YouTube ignora o pedido direto de qualidade; o que vale é o tamanho do player. Por isso o zoom da página
        é ajustado para a altura escolhida, o pedido direto também é feito e, se o player não obedecer, recarrega no mesmo ponto."""
        self._target_height = int(height) if height else AUTO_HEIGHT
        self._apply_zoom()
        self._js(f"quality('{playback.level_from_height(height) if height else 'default'}')")
        self._wanted_height = int(height) if height else None
        if self._wanted_height:
            self._quality_timer.start()
        else:
            self._quality_timer.stop()

    def _check_quality(self):
        wanted = self._wanted_height
        if wanted is None or not self._ready or self._video_id is None:
            return
        if self._height == wanted:
            return
        # o YouTube não trocou: recarrega no mesmo ponto; o tamanho virtual já está certo e define a qualidade inicial
        self._wanted_height = None  # uma tentativa só
        self._ready = False
        self._start_page(self._video_id, self._position)

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
        self._quality_timer.stop()
        self._overlay_timer.stop()
        self._release_overlay_owner()
        self._ready = self._playing = False
        view, page = self._view, self._page
        overlay, self._overlay = self._overlay, None
        view.setParent(None)
        view.deleteLater()
        if overlay is not None:
            overlay.hide()
            overlay.deleteLater()
        page.deleteLater()  # o perfil é filho da página e sai depois dela
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def run_script(self, script, callback=None):
        """Executa JavaScript na página (uso de testes e diagnóstico)."""
        if callback is None:
            self._page.runJavaScript(script)
        else:
            self._page.runJavaScript(script, callback)
