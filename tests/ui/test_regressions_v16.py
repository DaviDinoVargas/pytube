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
def test_quality_menu_is_offered_even_when_youtube_reports_no_levels(qtbot):
    no_levels = MOCK_API.replace("return ['hd1080', 'hd720', 'large', 'medium', 'auto'];", "return [];")
    assert no_levels != MOCK_API
    p = OnlinePlayer(api_script=no_levels, timeout_ms=15000)
    qtbot.addWidget(p)
    p.resize(480, 270)
    p.show()
    seen = []
    p.quality_changed.connect(lambda h, hs: seen.append(hs))
    ready(qtbot, p)
    qtbot.waitUntil(lambda: bool(seen), timeout=10000)
    assert seen[-1] == list(DEFAULT_HEIGHTS) and p.can_change_quality()
    p.shutdown()


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


def test_system_blur_is_a_safe_noop_outside_windows(qtbot):
    import sys

    from PySide6.QtWidgets import QMainWindow

    from app.styles.translucency import enable_system_blur

    win = QMainWindow()
    qtbot.addWidget(win)
    if not sys.platform.startswith("win"):
        assert enable_system_blur(win, True) is False
        assert enable_system_blur(win, False) is False


def test_gray_glass_window_is_translucent_but_panels_stay_readable():
    t = THEMES["frost"]
    assert t["translucent"] is True
    assert int(t["bg_start"].strip("rgba()").split(",")[-1]) < 200  # dá para ver o que está atrás
    assert int(t["surface"].strip("rgba()").split(",")[-1]) > 100  # mas os painéis escurecem o suficiente para ler


def test_glass_blur_setting_defaults_to_frosted_and_can_be_made_transparent(window_factory, settings):
    assert settings.glass_blur == "strong"
    w = window_factory()
    combo = w.settings_page.glass_combo
    assert [combo.itemData(i) for i in range(combo.count())] == ["strong", "none"]
    assert combo.currentData() == "strong" and combo.itemText(0).startswith("Fosco")
    combo.setCurrentIndex(combo.findData("none"))
    combo.activated.emit(combo.currentIndex())  # o clique do usuário
    assert settings.glass_blur == "none" and w.glass_blur_level == "none"
    settings.glass_blur = "light"  # valor de versões anteriores
    assert settings.glass_blur == "strong"


def test_translucent_backdrop_clears_the_previous_frame(qtbot):
    """O fundo mostrava a tela anterior do app: o quadro novo era pintado por cima do antigo."""
    from PySide6.QtGui import QImage

    from app.styles.backdrop import BackdropWidget

    widget = BackdropWidget(THEMES["frost"])
    qtbot.addWidget(widget)
    widget.resize(80, 60)
    image = QImage(80, 60, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.red)  # "quadro anterior" opaco
    widget.render(image)
    assert image.pixelColor(40, 30).alpha() < 255 and image.pixelColor(40, 30).red() < 200


def test_glass_is_reapplied_when_the_native_window_is_recreated_or_pages_change(window_factory, settings, monkeypatch):
    calls = []
    import app.ui.main_window as mw

    monkeypatch.setattr(mw, "enable_system_blur", lambda window, on, level="strong": calls.append((on, level)))
    settings.theme = "frost"
    w = window_factory()
    w._glass_timer.setInterval(1)
    calls.clear()

    def settle():
        w._glass_timer.stop()
        w._reapply_glass()

    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QShowEvent

    w.event(QEvent(QEvent.WinIdChange))
    assert w._glass_timer.isActive()  # recriou a janela nativa: reaplica
    settle()
    w.show_page("playlists")
    assert w._glass_timer.isActive()
    settle()
    w.watch_page.video_shown.emit("Título")
    assert w._glass_timer.isActive()
    settle()
    assert len(calls) == 3 and all(on and level == "strong" for on, level in calls)
    assert w.testAttribute(Qt.WA_TranslucentBackground)


def test_other_themes_never_touch_the_system_effect(window_factory, settings):
    w = window_factory()
    assert not w._theme.tokens["translucent"]
    w.show_page("playlists")
    assert not w._glass_timer.isActive()


def test_glass_rendering_is_prepared_only_for_the_gray_glass_on_windows(monkeypatch):
    import sys

    from PySide6.QtCore import QSettings

    import app.bootstrap as bootstrap

    saved = {"general/theme": "frost"}

    class FakeSettings:
        def __init__(self, *_):
            pass

        def value(self, key, default=None):
            return saved.get(key, default)

    monkeypatch.setattr(bootstrap, "QSettings", FakeSettings)
    monkeypatch.delenv("QT_WIDGETS_RHI", raising=False)
    monkeypatch.delenv("DINOTUBE_NO_RHI", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    bootstrap._prepare_glass_rendering()
    import os

    assert "QT_WIDGETS_RHI" not in os.environ
    monkeypatch.setattr(sys, "platform", "win32")
    bootstrap._prepare_glass_rendering()
    assert os.environ.get("QT_WIDGETS_RHI") == "1"
    monkeypatch.delenv("QT_WIDGETS_RHI")
    saved["general/theme"] = "dark"
    bootstrap._prepare_glass_rendering()
    assert "QT_WIDGETS_RHI" not in os.environ
    monkeypatch.setenv("DINOTUBE_NO_RHI", "1")
    saved["general/theme"] = "frost"
    bootstrap._prepare_glass_rendering()
    assert "QT_WIDGETS_RHI" not in os.environ


@needs_web
def test_online_surface_refresh_keeps_the_video_and_the_player_alive(qtbot, player):
    ready(qtbot, player)
    player.play()
    qtbot.waitUntil(lambda: player.is_playing(), timeout=10000)
    player.refresh_surface()
    qtbot.wait(400)
    assert player._view.isVisible() and player._ready and player.is_playing()
