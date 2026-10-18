import pytest
from PySide6.QtCore import Qt, QUrl

from app.i18n import Translator
from app.styles.tokens import THEMES
from app.styles.translucency import set_window_translucent
from app.ui.player.controls import PlayerControls

try:
    from app.ui.player.online_player import DEFAULT_HEIGHTS, EmbedPage, OnlinePlayer
    from PySide6.QtWebEngineCore import QWebEngineProfile

    WEBENGINE = True
except Exception:  # pragma: no cover
    WEBENGINE = False

from tests.yt_mock import MOCK_API

VID = "dQw4w9WgXcQ"
needs_web = pytest.mark.skipif(not WEBENGINE, reason="QtWebEngine indisponível")


@pytest.fixture
def player(qtbot):
    p = OnlinePlayer(api_script=MOCK_API, timeout_ms=15000)
    qtbot.addWidget(p)
    p.resize(480, 270)
    p.show()
    yield p
    p.shutdown()


def ready(qtbot, player):
    with qtbot.waitSignal(player.loaded, timeout=30000):
        player.load(VID, 0)


@needs_web
def test_navigation_permissions_are_counted_so_back_to_back_loads_are_not_lost(qtbot):
    """Sair e entrar rápido pedia duas cargas seguidas: a segunda era recusada e o player ficava preto."""
    page = EmbedPage(QWebEngineProfile())
    page.allow_next_load()
    page.allow_next_load()
    assert page.acceptNavigationRequest(QUrl("data:text/html,a"), 0, True) is True
    assert page.acceptNavigationRequest(QUrl("data:text/html,b"), 0, True) is True
    assert page.acceptNavigationRequest(QUrl("https://evil.example/"), 0, True) is False  # navegação da página: recusada
    assert page.acceptNavigationRequest(QUrl("https://www.youtube.com/embed/x"), 0, False) is True  # subquadro permitido
    page.deleteLater()


@needs_web
def test_quick_stop_then_load_still_shows_the_new_video(qtbot, player):
    ready(qtbot, player)
    player.stop()
    with qtbot.waitSignal(player.loaded, timeout=30000):
        player.load(VID, 0)  # logo após o stop, sem esperar a página em branco
    assert player._ready


@needs_web
def test_quality_menu_is_offered_even_when_youtube_reports_no_levels(qtbot, player):
    assert list(DEFAULT_HEIGHTS)[:2] == [1080, 720]
    ready(qtbot, player)
    player.run_script("window.__mock.getAvailableQualityLevels = function () { return []; }")
    seen = []
    player.quality_changed.connect(lambda h, hs: seen.append(hs))
    qtbot.waitUntil(lambda: bool(seen), timeout=10000)
    assert seen[-1] == list(DEFAULT_HEIGHTS)


@needs_web
def test_choosing_a_quality_the_player_ignores_reloads_at_the_same_point(qtbot, player):
    ready(qtbot, player)
    player.seek(42)
    qtbot.waitUntil(lambda: player.position() >= 41, timeout=10000)
    player.run_script("window.__mock.setPlaybackQuality = function () {}; window.__mock.setPlaybackQualityRange = function () {};")
    player._quality_timer.setInterval(200)
    with qtbot.waitSignal(player.loaded, timeout=30000):
        player.set_quality(480)
    assert player.target_height == 480


@needs_web
def test_toggle_uses_the_live_player_state_not_the_cached_one(qtbot, player):
    ready(qtbot, player)
    player.play()
    qtbot.waitUntil(lambda: player.is_playing(), timeout=10000)
    player._playing = False  # estado em cache desatualizado (o usuário clicou no vídeo)
    player.toggle()  # o player está tocando de verdade: deve pausar
    qtbot.waitUntil(lambda: not player.is_playing(), timeout=10000)
    player.toggle()
    qtbot.waitUntil(lambda: player.is_playing(), timeout=10000)


@needs_web
def test_buffering_counts_as_playing(qtbot, player):
    ready(qtbot, player)
    player._on_state(3)
    assert player.is_playing() is True
    player._on_state(2)
    assert player.is_playing() is False


@needs_web
def test_load_timeout_retries_before_failing(qtbot):
    import app.ui.player.online_player as op

    p = OnlinePlayer(api_script="/* nunca chama onYouTubeIframeAPIReady */", timeout_ms=op.RETRY_MS + 1000)
    qtbot.addWidget(p)
    p.show()
    p.load(VID, 0)
    p._on_load_timeout()
    assert p._retries == 1
    p._on_load_timeout()
    assert p._retries == 2
    errors = []
    p.error.connect(lambda code, detail: errors.append(code))
    p._on_load_timeout()
    assert errors == ["network"]
    p.shutdown()


def test_controls_keep_open_quality_menu_while_player_reports(qtbot):
    controls = PlayerControls(Translator("pt-BR"), THEMES["dark"])
    qtbot.addWidget(controls)
    controls.show()
    controls.set_quality(720, [1080, 720, 480], True)
    menu = controls.quality_button.menu()
    first = list(menu.actions())
    controls.set_quality(720, [1080, 720, 480], True)  # o mesmo aviso, de novo (duas vezes por segundo)
    controls.set_status(80, False, 1.0)
    controls.set_status(80, False, 1.0)
    assert list(menu.actions()) == first
    controls.set_quality(480, [1080, 720, 480], True)
    assert list(menu.actions()) != first  # mudança real reconstrói


def test_window_translucency_toggles(qtbot):
    from PySide6.QtWidgets import QMainWindow

    win = QMainWindow()
    qtbot.addWidget(win)
    assert set_window_translucent(win, True) is True
    assert win.testAttribute(Qt.WA_TranslucentBackground)
    assert set_window_translucent(win, True) is False
    win.show()
    assert set_window_translucent(win, False) is True
    assert not win.testAttribute(Qt.WA_TranslucentBackground) and win.isVisible()
    win.close()
