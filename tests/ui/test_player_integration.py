"""Player de ponta a ponta com motores REAIS: QtMultimedia tocando mídia gerada e o QtWebEngine com a API simulada."""

import pytest
from PySide6.QtWidgets import QApplication

from app.bootstrap import create_window
from app.infrastructure.providers.chain import ProviderChain
from app.services.storage_service import StorageManager
from app.services.thumbnail_service import ThumbnailService
from app.ui.player.local_player import LocalPlayer
from tests.fakes import VID, FakeProvider, make_stub_player
from tests.media import HAS_FFMPEG, make_media
from tests.yt_mock import MOCK_API

pytestmark = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg não instalado")

try:
    from app.ui.player.online_player import OnlinePlayer

    WEBENGINE = True
except Exception:  # pragma: no cover
    WEBENGINE = False


@pytest.fixture(scope="module")
def media(tmp_path_factory):
    return make_media(tmp_path_factory.mktemp("pi_short"), seconds=4)


@pytest.fixture(scope="module")
def long_media(tmp_path_factory):
    return make_media(tmp_path_factory.mktemp("pi_long"), seconds=12)


@pytest.fixture
def make(qtbot, settings, tmp_path):
    windows = []

    def build(online=None, provider=None):
        storage = StorageManager(settings, tmp_path / "appdata")
        storage.configure(tmp_path / "lib", "folder", "sqlite")
        provider = provider or FakeProvider("fake")
        options = {"local_factory": LocalPlayer, "online_factory": online or make_stub_player}
        w = create_window(QApplication.instance(), settings, storage, ProviderChain([provider]), ThumbnailService(lambda u: b""), player_options=options)
        qtbot.addWidget(w)
        w.show()
        windows.append(w)
        return w, provider

    yield build
    for w in windows:
        w.close()  # encerra o Chromium na ordem certa


def attach(w, provider, source, name="v.mp4"):
    video, _ = w.library.save_info(provider.fetch_info(VID))
    target = w.library.layout.videos / name
    target.write_bytes(source.read_bytes())
    return w.library.attach_local_file(video.id, target, "180p")


def test_local_file_plays_with_real_engine_and_reports_quality(qtbot, make, media):
    w, provider = make()
    video = attach(w, provider, media["progressive_mp4"])
    player = w.watch_page.player
    heights = []
    player.height_changed.connect(heights.append)
    w.open_saved_video(video.id)
    qtbot.waitUntil(lambda: player.controls._playing, timeout=15000)
    qtbot.waitUntil(lambda: player._pos > 0.5, timeout=15000)
    assert player.kind == "local" and player.controls.source_chip.text() == "Local"
    assert player.controls.time_label.text().endswith("/ 0:04")
    qtbot.waitUntil(lambda: bool(heights), timeout=10000)
    assert heights[0] == 180 and player.controls.quality_button.text() == "180p"  # altura real do arquivo
    assert not player.controls.quality_button.menu().actions()[0].isEnabled()


def test_position_is_saved_and_playback_resumes_from_it(qtbot, make, long_media):
    w, provider = make()
    video = attach(w, provider, long_media["progressive_mp4"])
    player = w.watch_page.player
    w.open_saved_video(video.id)
    qtbot.waitUntil(lambda: player._pos > 1.0, timeout=15000)
    player.stop()
    saved = w.progress.get(video.id)
    assert saved.duration >= 11.5 and saved.position > 1.0  # gravou onde parou
    w.progress.save(video.id, 6.0, 12.0)  # posição acima do mínimo de retomada (5 s)
    w.open_saved_video(video.id)
    assert player.notice.isVisible() and "0:06" in player.notice_label.text()
    qtbot.waitUntil(lambda: player._pos >= 5.7, timeout=15000)  # o motor real voltou ao ponto salvo


def test_watching_to_the_end_marks_watched(qtbot, make, media):
    w, provider = make()
    video = attach(w, provider, media["progressive_mp4"])
    player = w.watch_page.player
    w.open_saved_video(video.id)
    qtbot.waitUntil(lambda: w.progress.get(video.id) is not None and w.progress.get(video.id).watched, timeout=30000)
    assert w.progress.get(video.id).position == 0.0
    w.open_saved_video(video.id)
    assert not player.notice.isVisible()  # assistido: recomeça sem aviso


def test_corrupt_local_file_offers_online_instead_of_failing_silently(qtbot, make, media):
    w, provider = make()
    video = attach(w, provider, media["garbage"], name="ruim.mp4")
    player = w.watch_page.player
    w.open_saved_video(video.id)
    qtbot.waitUntil(lambda: player.stack.currentWidget() is player.message, timeout=15000)
    assert [b.text() for b in player.message.buttons][1] == "Assistir online"
    player.message.buttons[1].click()
    assert player.kind == "online"


def test_seek_slider_moves_real_playback(qtbot, make, long_media):
    w, provider = make()
    video = attach(w, provider, long_media["progressive_mp4"])
    player = w.watch_page.player
    w.open_saved_video(video.id)
    qtbot.waitUntil(lambda: player._dur > 11, timeout=15000)
    player.controls.seek_slider.setValue(800)
    player.controls._seeking = True
    player.controls._commit_seek()
    qtbot.waitUntil(lambda: player._pos >= 9.0, timeout=15000)


@pytest.mark.skipif(not WEBENGINE, reason="QtWebEngine indisponível")
def test_online_embed_with_real_webengine_and_mock_youtube_api(qtbot, make):
    w, provider = make(online=lambda: OnlinePlayer(api_script=MOCK_API))
    player = w.watch_page.player
    heights = []
    player.height_changed.connect(heights.append)
    w.top_bar.url_input.setText(f"https://youtu.be/{VID}")
    w.top_bar.open_button.click()
    qtbot.waitUntil(lambda: player.kind == "online", timeout=15000)
    qtbot.waitUntil(lambda: bool(heights), timeout=30000)  # a página carregou e a ponte respondeu
    assert heights[0] == 720 and player.controls.quality_button.text() == "720p"
    player.controls.play_button.click()
    qtbot.waitUntil(lambda: player.controls._playing and player._pos >= 1.0, timeout=15000)
    assert player.controls.time_label.text().endswith("/ 3:32")
    texts = [a.text() for a in player.controls.quality_button.menu().actions()]
    assert texts[:2] == ["Automática", "1080p"]
    next(a for a in player.controls.quality_button.menu().actions() if a.text() == "1080p").trigger()
    qtbot.waitUntil(lambda: heights[-1] == 1080, timeout=15000)  # a troca foi confirmada pelo player
    player.controls.volume_slider.setValue(30)
    player.controls.speed_button.menu().actions()[4].trigger()  # 1.5×
    qtbot.waitUntil(lambda: player.controls._rate == 1.5, timeout=15000)


@pytest.mark.skipif(not WEBENGINE, reason="QtWebEngine indisponível")
def test_embed_blocked_error_from_real_page_shows_alternatives(qtbot, make):
    w, provider = make(online=lambda: OnlinePlayer(api_script=MOCK_API))
    player = w.watch_page.player
    w.top_bar.url_input.setText(f"https://youtu.be/{VID}")
    w.top_bar.open_button.click()
    qtbot.waitUntil(lambda: player.kind == "online" and player._online._ready, timeout=30000)
    player._online.run_script("window.__mock.fail(150)")
    qtbot.waitUntil(lambda: player.stack.currentWidget() is player.message, timeout=15000)
    assert [b.text() for b in player.message.buttons] == ["Assistir com player próprio", "Abrir no navegador"]
