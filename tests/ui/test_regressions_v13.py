import pytest
from PySide6.QtCore import Qt

from app.ui.pages.categories_page import CARD_HEIGHT, CARD_WIDTH, CollectionCard
from tests.fakes import FakeProvider


@pytest.fixture
def w(window_factory):
    return window_factory()


def add(w, i, title=None):
    video, _ = w.library.save_info(FakeProvider("f", title=title or f"Vídeo {i}").fetch_info(f"vid{i:08d}"))
    return video


# ======================= vídeo que toca "em lugar nenhum" =======================
def test_leaving_before_the_info_arrives_never_starts_the_player(w, qtbot):
    """Abrir um link, sair na hora e a resposta de rede chegar depois: nada pode tocar."""
    wp = w.watch_page
    w._on_video_requested("zzzzzzzzzzz")  # não está na biblioteca: busca o vídeo na rede
    assert w.current_page == "watch"
    w.show_page("home")  # saiu imediatamente
    qtbot.wait(400)
    assert wp.player.is_idle() and wp.player._backend is None and wp._info is None


def test_player_open_is_postponed_while_the_page_is_hidden_and_runs_when_it_shows(w):
    wp = w.watch_page
    v = add(w, 1)
    w.show_page("home")
    wp.open_saved(v.id)  # abertura com a página escondida
    assert wp.player._backend is None and wp._player_pending
    w.show_page("watch")
    assert wp.player.video.id == v.id and not wp._player_pending


def test_late_stream_answer_after_stop_does_not_start_playing(w):
    v = add(w, 1)
    w.open_saved_video(v.id)
    player = w.watch_page.player
    token = player._request
    player.stop()
    player._on_stream_ready(token, ("https://x.googlevideo.com/v", 360), 0.0)
    assert player._backend is None and player._kind == ""


def test_leaving_the_watch_page_stops_the_online_backend_for_real(w):
    v = add(w, 1)
    w.open_saved_video(v.id)
    stub = w.watch_page.player._backend
    w.show_page("library")
    assert "stop" in stub.names() and not stub.is_playing()


def test_loading_screen_is_cleared_when_leaving(w):
    wp = w.watch_page
    w._on_video_requested("yyyyyyyyyyy")
    w.show_page("home")
    assert wp.stack.currentIndex() == 3  # tela vazia, não a de 'carregando'


# ======================= cartões da página de playlists =======================
def test_all_collection_cards_have_the_same_size(w):
    for i in range(1, 4):
        add(w, i)
    pl = w.org.create_playlist("Nome de playlist bem comprido que quebra a linha", "Descrição " * 30)
    w.org.create_playlist("Curta")
    w.org.add_to_playlist(pl.id, [1])
    w.show_page("playlists")
    page = w.pages["playlists"]
    page.refresh()
    cards = page.findChildren(CollectionCard)
    assert len(cards) >= 6  # 4 inteligentes + 2 manuais
    assert {(c.width(), c.height()) for c in cards} == {(CARD_WIDTH, CARD_HEIGHT)}


def test_categories_cards_also_share_the_size(w):
    w.org.create_category("A", "x " * 80)
    w.org.create_category("B")
    w.show_page("categories")
    w.pages["categories"].refresh()
    assert len({c.height() for c in w.pages["categories"].findChildren(CollectionCard)}) == 1


# ======================= modo cinema: texto centralizado =======================
def test_cinema_text_block_is_centered_under_the_player_with_reading_width(w):
    w.resize(1400, 850)
    w.show_page("settings")
    w.settings_page.layout_buttons["cinema"].click()
    v = add(w, 1)
    w.open_saved_video(v.id)
    wp = w.watch_page
    assert wp.body_holder.maximumWidth() == 920
    holder = wp.body_holder.geometry()
    page_width = wp.stack.currentWidget().width()
    left, right = holder.left(), page_width - holder.right()
    assert holder.width() <= 920 and abs(left - right) <= 6 and left > 100


def test_text_block_is_left_aligned_and_unbounded_outside_cinema(w):
    v = add(w, 1)
    w.open_saved_video(v.id)
    wp = w.watch_page
    assert wp.body_holder.maximumWidth() > 5000 and wp.body_holder.geometry().left() == 0
