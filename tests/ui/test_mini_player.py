import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtCore import QEvent

from app.domain.models import Progress
from tests.fakes import FakeProvider


@pytest.fixture
def w(window_factory):
    return window_factory()


def add(w, i):
    video, _ = w.library.save_info(FakeProvider("f", title=f"Vídeo {i}").fetch_info(f"vid{i:08d}"))
    return video


def play(w, i=1):
    v = add(w, i)
    w.open_saved_video(v.id)
    w.watch_page.player._backend.loaded.emit()
    return v


def test_mini_player_floats_on_top_and_leaves_the_video_page(w):
    v = play(w)
    player = w.watch_page.player
    player.enter_mini()
    assert player.is_mini and player.parentWidget() is None
    assert player.windowFlags() & Qt.WindowStaysOnTopHint and player.windowFlags() & Qt.FramelessWindowHint
    assert not player.mini_bar.isHidden() and player.mini_bar.title.text() == v.title
    assert w.current_page != "watch"  # a janela principal volta para a página anterior
    assert player._backend is not None  # o vídeo continua carregado


def test_mini_player_keeps_playing_when_navigating(w):
    play(w)
    player = w.watch_page.player
    player.enter_mini()
    stub = player._backend
    w.show_page("library")
    w.show_page("home")
    assert player.is_mini and "stop" not in stub.names() and player._backend is stub


def test_mini_controls_keep_only_the_essentials(w):
    play(w)
    player = w.watch_page.player
    c = player.controls
    player.enter_mini()
    assert c.volume_slider.isHidden() and c.speed_button.isHidden() and c.quality_button.isHidden()
    assert c.fullscreen_button.isHidden() and not c.play_button.isHidden() and not c.mini_button.isHidden()
    assert player.width() == 420 and player.stack.height() == int(420 * 9 / 16)
    player.exit_mini()
    assert not c.volume_slider.isHidden() and not c.fullscreen_button.isHidden()


def test_expand_returns_the_player_to_the_video_page(w, qtbot):
    play(w)
    player = w.watch_page.player
    player.enter_mini()
    with qtbot.waitSignal(player.expand_requested, timeout=1000):
        player.mini_bar.expand_button.click()
    assert not player.is_mini and w.current_page == "watch"
    assert player.parentWidget() is not None and not (player.windowFlags() & Qt.WindowStaysOnTopHint)
    assert player._backend is not None


def test_close_stops_the_video_and_saves_the_position(w):
    v = play(w)
    player = w.watch_page.player
    player._on_position(player._backend, 30.0, 100.0)
    player.enter_mini()
    player.mini_bar.close_button.click()
    assert not player.is_mini and player._backend is None
    assert w.progress.get(v.id).position == pytest.approx(30.0)


def test_opening_another_video_leaves_mini_and_loads_it(w):
    play(w, 1)
    other = add(w, 2)
    w.watch_page.player.enter_mini()
    w.open_saved_video(other.id)
    player = w.watch_page.player
    assert not player.is_mini and w.current_page == "watch" and player.video.id == other.id


def test_mini_needs_something_loaded_and_is_not_combined_with_fullscreen(w):
    player = w.watch_page.player
    player.enter_mini()
    assert not player.is_mini  # nada tocando
    play(w)
    player.enter_fullscreen()
    player.enter_mini()
    assert not player.is_mini
    player.exit_fullscreen()


def test_toggle_by_button_and_shortcut_i(w):
    play(w)
    player = w.watch_page.player
    player.controls.mini_button.click()
    assert player.is_mini
    player.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_I, Qt.NoModifier))
    assert not player.is_mini and w.current_page == "watch"


def test_playlist_advances_inside_the_mini_player(w):
    a, b = add(w, 1), add(w, 2)
    p = w.org.create_playlist("Lista")
    w.org.add_to_playlist(p.id, [a.id, b.id])
    w.open_saved_video(a.id, playlist_id=p.id)
    player = w.watch_page.player
    player._backend.loaded.emit()
    player.enter_mini()
    w.show_page("library")
    player._on_ended(player._backend)
    assert player.is_mini and player.video.id == b.id and w.current_page == "library"


def test_shutdown_closes_the_mini_window(w):
    play(w)
    player = w.watch_page.player
    player.enter_mini()
    player.shutdown()
    assert not player.is_mini


def test_mini_texts_exist_in_both_languages(w):
    from app.i18n import Translator

    for lang in ("pt-BR", "en"):
        tr = Translator(lang)
        for key in ("player.mini", "player.mini_expand", "player.mini_close"):
            assert tr.t(key) != key
