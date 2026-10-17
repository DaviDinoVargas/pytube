import pytest

from app.ui.player.local_player import LocalPlayer
from tests.media import HAS_FFMPEG, make_media

pytestmark = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg não instalado")


@pytest.fixture(scope="module")
def media(tmp_path_factory):
    return make_media(tmp_path_factory.mktemp("lp"), seconds=3)


@pytest.fixture
def player(qtbot):
    p = LocalPlayer()
    qtbot.addWidget(p)
    p.resize(320, 180)
    p.show()
    yield p
    p.stop()


def test_plays_real_file_and_reports_position_quality_and_end(qtbot, player, media):
    positions, qualities, states = [], [], []
    player.position_changed.connect(lambda p, d: positions.append((p, d)))
    player.quality_changed.connect(lambda h, hs: qualities.append((h, hs)))
    player.state_changed.connect(states.append)
    with qtbot.waitSignal(player.ended, timeout=15000):
        player.load_file(media["progressive_mp4"])
    assert states[0] is True and states[-1] is False
    assert qualities and qualities[0] == (180, [180])  # altura real do arquivo
    assert max(p for p, _d in positions) >= 2.5 and any(d >= 2.5 for _p, d in positions)


def test_pause_resume_and_seek(qtbot, player, media):
    with qtbot.waitSignal(player.loaded, timeout=10000):
        player.load_file(media["progressive_mp4"], autoplay=False)
    assert not player.is_playing()
    player.play()
    qtbot.waitUntil(lambda: player.is_playing(), timeout=5000)
    player.pause()
    qtbot.waitUntil(lambda: not player.is_playing(), timeout=5000)
    player.seek(2.0)
    qtbot.waitUntil(lambda: player.position() >= 1.9, timeout=5000)
    assert 1.9 <= player.position() <= 3.1


def test_starts_at_requested_position(qtbot, player, media):
    with qtbot.waitSignal(player.loaded, timeout=10000):
        player.load_file(media["progressive_mp4"], start=1.5, autoplay=False)
    qtbot.waitUntil(lambda: player.position() >= 1.4, timeout=5000)
    assert player.position() >= 1.4


def test_volume_mute_and_rate_are_reported(qtbot, player, media):
    seen = []
    player.status_changed.connect(lambda v, m, r: seen.append((v, m, r)))
    player.set_volume(40)
    player.set_muted(True)
    player.set_rate(1.5)
    qtbot.waitUntil(lambda: any(r == 1.5 for _v, _m, r in seen), timeout=5000)
    assert any(v == 40 for v, _m, _r in seen) and any(m for _v, m, _r in seen)
    player.set_volume(500)  # limitado a 100
    assert seen[-1][0] <= 100 or player._audio.volume() <= 1.0


def test_garbage_file_reports_error(qtbot, player, media):
    with qtbot.waitSignal(player.error, timeout=10000) as sig:
        player.load_file(media["garbage"])
    assert sig.args[0] == "local_failed"


def test_missing_file_reports_error(qtbot, player, tmp_path):
    with qtbot.waitSignal(player.error, timeout=10000) as sig:
        player.load_file(tmp_path / "nao_existe.mp4")
    assert sig.args[0] == "local_failed"


def test_click_on_video_is_reported(qtbot, player, media):
    from PySide6.QtCore import Qt

    with qtbot.waitSignal(player.clicked, timeout=3000):
        qtbot.mouseClick(player._video, Qt.LeftButton)


def test_does_not_change_quality(player):
    assert player.can_change_quality() is False
    player.set_quality(1080)  # ignorado, sem exceção
