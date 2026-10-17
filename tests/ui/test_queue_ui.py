import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QMenu

from app.services.queue_service import QueueService
from tests.fakes import FakeProvider


@pytest.fixture
def w(window_factory):
    return window_factory()


def add(w, i, title=None):
    video, _ = w.library.save_info(FakeProvider("f", title=title or f"Vídeo {i}").fetch_info(f"vid{i:08d}"))
    return video


def titles(panel):
    return [panel.list.item(i).text() for i in range(panel.list.count())]


# ======================= serviço =======================
def test_service_adds_orders_and_persists_in_settings(w, settings):
    a, b, c = add(w, 1), add(w, 2), add(w, 3)
    w.queue.add([a.id, b.id])
    w.queue.add([c.id], play_next=False)
    w.queue.set_order([c.id, a.id, b.id])
    assert settings.queue_ids == (c.id, a.id, b.id)
    reopened = QueueService(w.library, settings)
    assert reopened.ids == [c.id, a.id, b.id]


def test_service_ignores_unknown_ids_and_drops_removed_videos(w):
    a, b = add(w, 1), add(w, 2)
    w.queue.add([a.id, b.id, 999])
    assert w.queue.ids == [a.id, b.id]
    w.library.remove(a.id)
    assert w.queue.ids == [b.id] and [v.id for v in w.queue.videos()] == [b.id]


def test_service_current_is_saved_and_only_marks_queued_videos(w, settings):
    a, b = add(w, 1), add(w, 2)
    w.queue.add([a.id])
    w.queue.set_current(a.id)
    assert settings.queue_current == a.id
    w.queue.set_current(b.id)  # fora da fila
    assert w.queue.current is None and w.queue.ids == [a.id]


def test_service_emits_changed(w, qtbot):
    a = add(w, 1)
    with qtbot.waitSignal(w.queue.changed, timeout=1000):
        w.queue.add([a.id])
    with qtbot.waitSignal(w.queue.changed, timeout=1000):
        w.queue.clear()


# ======================= menus e botões =======================
def test_card_menu_offers_add_to_queue_and_play_next(w):
    add(w, 1)
    w.show_page("library")
    w.pages["library"].refresh()
    card = w.pages["library"].cards()[0]
    menu = QMenu()
    card._fill_menu(menu)
    labels = [a.text() for a in menu.actions()]
    assert "Adicionar à fila" in labels and "Tocar em seguida" in labels


def test_video_actions_add_to_the_queue_and_show_a_message(w):
    a, b = add(w, 1), add(w, 2)
    w._on_video_action(a.id, "queue_add")
    w._on_video_action(b.id, "queue_next")
    assert w.queue.ids == [a.id, b.id]
    assert "seguida" in w.top_bar.feedback.text().lower()
    w._on_video_action(a.id, "queue_add")
    assert "fila" in w.top_bar.feedback.text().lower()


def test_play_next_goes_right_after_the_playing_video(w):
    a, b, c = add(w, 1), add(w, 2), add(w, 3)
    w.queue.add([a.id, b.id])
    w.open_saved_video(a.id)
    w._on_video_action(c.id, "queue_next")
    assert w.queue.ids == [a.id, c.id, b.id]


def test_watch_page_queue_button_adds_the_open_video(w):
    a = add(w, 1)
    w.open_saved_video(a.id)
    w.watch_page.queue_button.click()
    assert w.queue.ids == [a.id]


# ======================= painel da fila =======================
def test_panel_hidden_when_empty_and_visible_with_items_in_classic_layout(w):
    a, b = add(w, 1), add(w, 2)
    w.open_saved_video(a.id)
    assert w.watch_page.queue_panel.isHidden()
    w.queue.add([a.id, b.id])
    panel = w.watch_page.queue_panel
    assert not panel.isHidden() and len(titles(panel)) == 2
    assert "▶" in titles(panel)[0] and "Vídeo 1" in titles(panel)[0]
    assert "5" not in panel.title_label.text() and "2" in panel.title_label.text()


def test_clicking_a_queue_item_plays_it_and_marks_it_current(w):
    a, b = add(w, 1), add(w, 2)
    w.queue.add([a.id, b.id])
    w.open_saved_video(a.id)
    panel = w.watch_page.queue_panel
    panel.list.itemDoubleClicked.emit(panel.list.item(1))
    assert w.watch_page.player.video.id == b.id and w.queue.current == b.id
    assert titles(panel)[1].startswith("▶")


def test_remove_button_delete_key_and_clear(w):
    a, b, c = add(w, 1), add(w, 2), add(w, 3)
    w.queue.add([a.id, b.id, c.id])
    w.open_saved_video(a.id)
    panel = w.watch_page.queue_panel
    panel.list.setCurrentRow(1)
    panel.remove_button.click()
    assert w.queue.ids == [a.id, c.id]
    panel.list.setCurrentRow(1)
    panel.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier))
    assert w.queue.ids == [a.id]
    panel.clear_button.click()
    assert w.queue.ids == [] and panel.isHidden()


def test_reordering_in_the_panel_updates_the_queue(w):
    a, b, c = add(w, 1), add(w, 2), add(w, 3)
    w.queue.add([a.id, b.id, c.id])
    w.open_saved_video(a.id)
    panel = w.watch_page.queue_panel
    item = panel.list.takeItem(2)
    panel.list.insertItem(0, item)
    panel.order_changed.emit(panel.ids())
    assert w.queue.ids == [c.id, a.id, b.id]


def test_previous_and_next_buttons_walk_the_queue(w):
    a, b, c = add(w, 1), add(w, 2), add(w, 3)
    w.queue.add([a.id, b.id, c.id])
    w.open_saved_video(b.id)
    panel = w.watch_page.queue_panel
    panel.next_button.click()
    assert w.watch_page.player.video.id == c.id
    panel.next_button.click()  # fim da fila: nada acontece
    assert w.watch_page.player.video.id == c.id
    panel.previous_button.click()
    panel.previous_button.click()
    assert w.watch_page.player.video.id == a.id


# ======================= reprodução =======================
def test_video_that_ends_plays_the_next_in_the_queue(w):
    a, b = add(w, 1), add(w, 2)
    w.queue.add([a.id, b.id])
    w.open_saved_video(a.id)
    player = w.watch_page.player
    player._on_ended(player._backend)
    assert player.video.id == b.id and w.queue.current == b.id


def test_end_of_queue_does_not_loop_and_respects_autoplay_setting(w, settings):
    a, b = add(w, 1), add(w, 2)
    w.queue.add([a.id, b.id])
    w.open_saved_video(b.id)
    player = w.watch_page.player
    player._on_ended(player._backend)
    assert player.video.id == b.id
    settings.autoplay_next = False
    w.open_saved_video(a.id)
    player._on_ended(player._backend)
    assert player.video.id == a.id


def test_queue_wins_over_the_playlist_and_falls_back_to_it_at_the_end(w):
    a, b, c = add(w, 1), add(w, 2), add(w, 3)
    pl = w.org.create_playlist("L")
    w.org.add_to_playlist(pl.id, [a.id, b.id, c.id])
    w.queue.add([a.id, c.id])
    w.open_saved_video(a.id, playlist_id=pl.id)
    player = w.watch_page.player
    player._on_ended(player._backend)
    assert player.video.id == c.id  # a fila manda: pulou o b da playlist
    w.queue.remove(c.id)
    w.open_saved_video(a.id, playlist_id=pl.id)
    w.queue.clear()
    player._on_ended(player._backend)
    assert player.video.id == b.id  # sem fila, a playlist segue


def test_queue_advances_inside_the_mini_player_without_changing_page(w):
    a, b = add(w, 1), add(w, 2)
    w.queue.add([a.id, b.id])
    w.open_saved_video(a.id)
    player = w.watch_page.player
    player._backend.loaded.emit()
    player.enter_mini()
    w.show_page("library")
    player._on_ended(player._backend)
    assert player.is_mini and player.video.id == b.id and w.current_page == "library" and w.queue.current == b.id


def test_opening_a_video_outside_the_queue_leaves_it_untouched(w):
    a, b = add(w, 1), add(w, 2)
    w.queue.add([a.id])
    w.open_saved_video(b.id)
    assert w.queue.ids == [a.id] and w.queue.current is None


def test_queue_survives_a_restart(window_factory, settings):
    w1 = window_factory()
    a, b = add(w1, 1), add(w1, 2)
    w1.queue.add([b.id, a.id])
    w1.open_saved_video(b.id)
    w2 = window_factory()
    assert w2.queue.ids == [b.id, a.id] and w2.queue.current == b.id
    assert len(titles(w2.watch_page.queue_panel)) == 2


# ======================= F. layout compacto =======================
def choose(w, key):
    w.show_page("settings")
    w.settings_page.layout_buttons[key].click()


def test_compact_shrinks_the_window_and_the_full_button_brings_it_back(w):
    w.resize(1280, 800)
    normal_min = w.minimumSize()
    choose(w, "compact")
    assert w.width() <= 500 and w.minimumWidth() < normal_min.width()
    assert w.sidebar.isHidden() and not w.top_bar.menu_button.isHidden() and w.top_bar.search_input.isHidden()
    w.watch_page.full_button.click()
    assert w.layouts.key == "classic" and w.width() == 1280 and w.minimumSize() == normal_min
    assert w.top_bar.menu_button.isHidden() and not w.top_bar.search_input.isHidden()


def test_full_window_returns_to_the_layout_used_before(w, settings):
    choose(w, "streaming")
    choose(w, "compact")
    assert settings.layout_before_compact == "streaming"
    w.watch_page.full_button.click()
    assert w.layouts.key == "streaming" and settings.layout == "streaming"


def test_compact_page_shows_player_title_and_queue_only(w):
    a = add(w, 1)
    w.queue.add([a.id])
    choose(w, "compact")
    w.open_saved_video(a.id)
    wp = w.watch_page
    assert wp.info_block.isHidden() and wp.meta_label.isHidden() and not wp.queue_panel.isHidden()
    assert wp.pin_button.isVisibleTo(wp) and wp.full_button.isVisibleTo(wp)
    c = wp.player.controls
    assert c.volume_slider.isHidden() and c.quality_button.isHidden() and c.mini_button.isHidden() and not c.fullscreen_button.isHidden()
    assert wp.title_label.property("compact") is True


def test_compact_queue_panel_is_shown_even_when_empty_with_a_hint(w):
    choose(w, "compact")
    assert w.current_page == "watch" and not w.watch_page.queue_panel.isHidden()
    assert "vazia" in w.watch_page.queue_panel.empty_label.text()


def test_leaving_compact_restores_the_watch_page(w):
    a = add(w, 1)
    choose(w, "compact")
    choose(w, "classic")
    w.open_saved_video(a.id)
    wp = w.watch_page
    assert not wp.info_block.isHidden() and wp.pin_button.isHidden() and wp.player.controls.volume_slider.isVisibleTo(wp.player.controls)
    assert wp.queue_panel.isHidden()  # fila vazia fora do compacto


def test_pin_keeps_the_window_on_top_only_in_compact_and_persists(w, settings):
    assert not w.layouts.keep_on_top
    choose(w, "compact")
    assert w.layouts.keep_on_top and w.watch_page.pin_button.isChecked()
    w.watch_page.pin_button.click()
    assert not w.layouts.keep_on_top and settings.compact_on_top is False
    w.watch_page.pin_button.click()
    assert w.layouts.keep_on_top and settings.compact_on_top is True
    w.watch_page.full_button.click()
    assert not w.layouts.keep_on_top  # nos outros layouts a janela nunca fica por cima


def test_compact_nav_menu_reaches_the_pages(w):
    choose(w, "compact")
    menu = w.top_bar.menu_button.menu()
    labels = [a.text() for a in menu.actions() if a.text()]
    assert "Biblioteca" in labels and "Configurações" in labels and "Fila de reprodução" in labels
    next(a for a in menu.actions() if a.text() == "Biblioteca").trigger()
    assert w.current_page == "library"
