import pytest

try:
    from app.ui.player.online_player import EmbedPage, OnlinePlayer, host_allowed
    from PySide6.QtCore import QUrl
    from PySide6.QtWebEngineCore import QWebEnginePage

    WEBENGINE = True
except Exception:  # pragma: no cover
    WEBENGINE = False

from tests.yt_mock import MOCK_API

pytestmark = pytest.mark.skipif(not WEBENGINE, reason="QtWebEngine indisponível")
VID = "dQw4w9WgXcQ"


@pytest.fixture
def player(qtbot):
    p = OnlinePlayer(api_script=MOCK_API, timeout_ms=15000)
    qtbot.addWidget(p)
    p.resize(480, 270)
    p.show()
    yield p
    p.shutdown()


def ready(qtbot, player, start=0):
    with qtbot.waitSignal(player.loaded, timeout=30000):
        player.load(VID, start)


def test_loads_page_and_bridge_connects(qtbot, player):
    ready(qtbot, player)
    assert player.duration() >= 0


def test_play_pause_and_position_via_bridge(qtbot, player):
    ready(qtbot, player)
    states = []
    player.state_changed.connect(states.append)
    player.play()
    qtbot.waitUntil(lambda: player.is_playing(), timeout=10000)
    qtbot.waitUntil(lambda: player.position() >= 1.0, timeout=10000)
    assert player.duration() == 212
    player.pause()
    qtbot.waitUntil(lambda: not player.is_playing(), timeout=10000)
    assert states[0] is True and states[-1] is False


def test_reports_real_quality_and_available_levels(qtbot, player):
    ready(qtbot, player)
    with qtbot.waitSignal(player.quality_changed, timeout=10000, check_params_cb=lambda h, hs: h == 720 and hs):
        pass
    assert player.current_height() == 720


def test_quality_change_is_requested_and_confirmed_by_player(qtbot, player):
    ready(qtbot, player)
    qtbot.waitUntil(lambda: player.current_height() == 720, timeout=10000)
    assert player.can_change_quality() is True
    with qtbot.waitSignal(player.quality_changed, timeout=10000, check_params_cb=lambda h, hs: h == 1080):
        player.set_quality(1080)
    assert player.current_height() == 1080


def test_seek_volume_mute_and_rate(qtbot, player):
    ready(qtbot, player)
    seen = []
    player.status_changed.connect(lambda v, m, r: seen.append((v, m, r)))
    player.seek(100)
    player.set_volume(35)
    player.set_muted(True)
    player.set_rate(1.5)
    qtbot.waitUntil(lambda: any(v == 35 and m and r == 1.5 for v, m, r in seen), timeout=10000)
    qtbot.waitUntil(lambda: player.position() >= 99, timeout=10000)


def test_start_position_is_passed_to_the_player(qtbot, player):
    ready(qtbot, player, start=42)
    result = []
    player.run_script("window.__mock.options.playerVars.start", result.append)
    qtbot.waitUntil(lambda: bool(result), timeout=10000)
    assert result == [42]


@pytest.mark.parametrize("code,expected", [(150, "embed_blocked"), (101, "embed_blocked"), (100, "unavailable")])
def test_player_errors_are_mapped(qtbot, player, code, expected):
    ready(qtbot, player)
    with qtbot.waitSignal(player.error, timeout=10000) as sig:
        player.run_script(f"window.__mock.fail({code})")
    assert sig.args == [expected, f"youtube:{code}"]


def test_times_out_when_the_youtube_player_never_answers(qtbot):
    p = OnlinePlayer(api_script="/* a API nunca carrega */", timeout_ms=400)
    qtbot.addWidget(p)
    p.show()
    with qtbot.waitSignal(p.error, timeout=15000) as sig:
        p.load(VID)
    assert sig.args[0] == "network"
    p.shutdown()


def test_invalid_id_never_reaches_the_page(qtbot, player):
    with pytest.raises(ValueError):
        player.load("abc'); alert(1);//")


def test_profile_is_temporary_and_page_is_locked_down(player):
    assert player._profile.isOffTheRecord()
    page = player._page
    assert page.acceptNavigationRequest(QUrl("https://evil.example/"), QWebEnginePage.NavigationType.NavigationTypeLinkClicked, True) is False
    assert page.acceptNavigationRequest(QUrl("https://www.youtube-nocookie.com/embed/x"), QWebEnginePage.NavigationType.NavigationTypeTyped, False) is True
    assert page.acceptNavigationRequest(QUrl("https://evil.example/frame"), QWebEnginePage.NavigationType.NavigationTypeTyped, False) is False
    assert page.createWindow(QWebEnginePage.WebWindowType.WebBrowserWindow) is None


@pytest.mark.parametrize("url,ok", [
    ("https://www.youtube.com/embed/x", True), ("https://www.youtube-nocookie.com/embed/x", True),
    ("https://i.ytimg.com/vi/x.jpg", True), ("https://rr1---sn.googlevideo.com/videoplayback", True),
    ("https://youtube.com.evil.com/x", False), ("https://evil.com/youtube.com", False), ("http://", False), ("", False),
])
def test_host_allowlist(url, ok):
    assert host_allowed(url) is ok


def js(qtbot, player, script):
    box = []
    player.run_script(script, box.append)
    qtbot.waitUntil(lambda: bool(box), timeout=10000)
    return box[0]


def test_stop_really_destroys_the_youtube_page(qtbot, player):
    """Pausar não basta: o autoplay de um player que ainda carrega ligaria o vídeo depois, sem ninguém assistindo."""
    ready(qtbot, player)
    player.play()
    qtbot.waitUntil(lambda: player.is_playing(), timeout=10000)
    player.stop()
    qtbot.waitUntil(lambda: player._page.url().toString() == "about:blank", timeout=10000)
    assert js(qtbot, player, "typeof window.__mock") == "undefined"
    assert not player.is_playing()


def test_stop_before_the_player_is_ready_cancels_it(qtbot, player):
    player.load(VID, 0)
    player.stop()  # sai da página "imediatamente"
    qtbot.wait(800)
    assert player._page.url().toString() == "about:blank" and not player._ready
    assert js(qtbot, player, "typeof window.__mock") == "undefined"


def test_default_quality_asks_youtube_for_full_hd_by_enlarging_the_page_viewport(qtbot, player):
    """O YouTube escolhe a resolução pelo tamanho do player em px CSS. Uma janela de 480 px enxergaria só 360p."""
    ready(qtbot, player)
    qtbot.waitUntil(lambda: abs(player._view.zoomFactor() - 0.25) < 0.01, timeout=10000)
    assert js(qtbot, player, "window.innerWidth") >= 1800
    assert player.target_height == 1080


def test_chosen_quality_changes_the_virtual_viewport(qtbot, player):
    ready(qtbot, player)
    player.resize(640, 360)
    qtbot.wait(300)
    player.set_quality(720)
    qtbot.waitUntil(lambda: abs(player._view.zoomFactor() - 640 / 1280) < 0.01, timeout=10000)
    qtbot.waitUntil(lambda: 1200 <= js(qtbot, player, "window.innerWidth") <= 1360, timeout=10000)
    player.set_quality(None)  # automático = até Full HD
    qtbot.waitUntil(lambda: abs(player._view.zoomFactor() - 640 / 1920) < 0.01, timeout=10000)


def test_zoom_is_clamped_and_follows_the_widget_size(qtbot):
    p = OnlinePlayer(api_script=MOCK_API)
    qtbot.addWidget(p)
    assert p.zoom_for(0) == 1.0
    assert p.zoom_for(100) == 0.25 and p.zoom_for(100000) == 5.0
    assert abs(p.zoom_for(1920) - 1.0) < 1e-9
    p.set_quality(480)
    assert p.css_width_for(480) == 853 and abs(p.zoom_for(853) - 1.0) < 0.01
    p.shutdown()
