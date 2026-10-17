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
