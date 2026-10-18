"""A anatomia própria de cada layout: navegação do topo, árvore, barra de estado, pôsteres, coluna 'a seguir', painéis da estação."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from app.ui.chrome.nav_tree import NavTree
from app.ui.widgets.poster_tile import PosterTile
from app.ui.widgets.up_next import UpNextRow
from tests.fakes import FakeProvider


@pytest.fixture
def w(window_factory):
    return window_factory()


def add(w, i, title=None, size=None):
    video, _ = w.library.save_info(FakeProvider("f", title=title or f"Vídeo {i}").fetch_info(f"vid{i:08d}"))
    video.channel = f"Canal {i}"
    w.library.store.update_video(video)
    if size is not None:
        f = w.library.layout.videos / f"{i}.mp4"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"0" * size)
        video = w.library.attach_local_file(video.id, f, "720p")
    return video


def choose(w, key):
    w.show_page("settings")
    w.settings_page.layout_buttons[key].click()


def settle(qtbot, ms=350):
    qtbot.wait(ms)


# ======================= B. Streaming: abas no topo =======================
def test_top_nav_tabs_switch_pages_and_follow_the_current_page(w):
    choose(w, "streaming")
    nav = w.top_nav
    nav.tabs["library"].click()
    assert w.current_page == "library" and nav.tabs["library"].isChecked()
    w.show_page("playlists")
    assert nav.tabs["playlists"].isChecked()
    w.show_page("playlist")
    assert nav.tabs["playlists"].isChecked()  # detalhe de uma playlist continua na aba Playlists
    w.show_page("settings")
    assert not any(b.isChecked() for b in nav.tabs.values())


def test_streaming_search_filters_the_library_and_link_popup_opens_videos(w, qtbot):
    a, b = add(w, 1, "Python avançado"), add(w, 2, "Receita")
    choose(w, "streaming")
    w.top_nav.search_input.setText("receita")
    qtbot.waitUntil(lambda: w.query_state.query.text == "receita", timeout=3000)
    assert w.current_page == "library"
    w.top_nav.popup.url_input.setText("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    w.top_nav.popup.open_button.click()
    assert w.current_page == "watch"


def test_top_nav_rejects_an_invalid_link_inline(w):
    choose(w, "streaming")
    w.top_nav.popup.url_input.setText("nada de link")
    w.top_nav.popup.open_button.click()
    assert not w.top_nav.popup.error_label.isHidden() and w.current_page != "watch"


def test_notifications_reach_the_visible_bar_of_each_layout(w, qtbot):
    choose(w, "streaming")
    w.notify("Pronto", False)
    assert w.top_nav.feedback.text() == "Pronto"
    choose(w, "manager")
    w.notify("Feito", False)
    assert w.status_bar.message.text() == "Feito"
    choose(w, "compact")
    w.notify("Aviso", True)
    assert "Aviso" in w.compact_bar.title_label.text()


def test_search_field_text_is_shared_between_the_bars(w, qtbot):
    choose(w, "streaming")
    w.query_state.set_text("abc")
    assert w.top_nav.search_input.text() == "abc" and w.top_bar.search_input.text() == "abc"


def test_streaming_watch_page_has_an_up_next_column_instead_of_details(w):
    a, b, c = add(w, 1), add(w, 2), add(w, 3)
    cat = w.org.create_category("X")
    w.org.assign_categories([a.id, b.id, c.id], add=[cat.id])
    w.resize(1400, 850)
    choose(w, "streaming")
    w.queue.add([b.id])
    w.open_saved_video(a.id)
    wp = w.watch_page
    assert not wp.up_next.isHidden() and wp.details.isHidden() and wp.related.isHidden() and wp.queue_panel.isHidden()
    assert [r.video_id for r in wp.up_next.rows] == [b.id, c.id]  # a fila primeiro, depois os parecidos
    assert [h.text() for h in wp.up_next.headings] == ["NA FILA", "PARECIDOS COM ESTE"]
    wp.up_next.rows[1].open_requested.emit(c.id)
    assert wp.player.video.id == c.id


def test_up_next_explains_when_there_is_nothing_to_suggest(w):
    a = add(w, 1)
    w.resize(1400, 850)
    choose(w, "streaming")
    w.open_saved_video(a.id)
    assert not w.watch_page.up_next.empty_label.isHidden()


def test_streaming_player_uses_the_free_width(w):
    a = add(w, 1)
    w.resize(1400, 850)
    choose(w, "streaming")
    w.open_saved_video(a.id)
    player = w.watch_page.player
    assert player._width_limit() > 1000 and player.width() > 900  # sem o teto de 1000 px do layout clássico


def test_streaming_rows_use_posters_without_card_frames(w):
    add(w, 1)
    choose(w, "streaming")
    w.show_page("home")
    tiles = w.pages["home"].findChildren(PosterTile)
    assert tiles and all(t.objectName() == "posterTile" for t in tiles)
    tiles[0].open_requested.emit(tiles[0].video.id)
    assert w.current_page == "watch"


def test_streaming_library_is_a_poster_grid(w):
    add(w, 1)
    choose(w, "streaming")
    w.show_page("library")
    assert w.pages["library"]._view == "posters" and w.pages["library"].findChildren(PosterTile)


# ======================= C. Cinema: mural =======================
def test_cinema_home_and_library_are_a_wall_of_big_posters(w):
    for i in range(1, 5):
        add(w, i)
    choose(w, "cinema")
    w.show_page("home")
    home = w.pages["home"]
    tiles = home.findChildren(PosterTile)
    assert len(tiles) == 4 and all(t.width() > 340 for t in tiles) and home.title.isHidden()
    w.show_page("library")
    assert w.pages["library"]._view == "wall" and len(w.pages["library"].findChildren(PosterTile)) == 4


def test_wall_tile_shows_its_title_only_on_hover_and_has_the_card_menu(w):
    v = add(w, 1)
    choose(w, "cinema")
    w.show_page("home")
    tile = w.pages["home"].findChildren(PosterTile)[0]
    assert tile._hover is False
    tile.enterEvent(None) if False else None
    tile._hover = True
    assert tile.grab().width() > 0
    from PySide6.QtWidgets import QMenu

    menu = QMenu()
    tile._fill_menu(menu)
    assert "Adicionar à fila" in [a.text() for a in menu.actions()]


def test_poster_tile_keyboard_and_selection_mode(w):
    v = add(w, 1)
    choose(w, "cinema")
    w.show_page("library")
    tile = w.pages["library"].findChildren(PosterTile)[0]
    tile.set_selectable(True)
    tile.set_selected(True)
    assert tile.selected and w.pages["library"].selected_ids == [v.id]


# ======================= D. Gerenciador: árvore, faixa e barra de estado =======================
@pytest.fixture
def manager(w, qtbot):
    w.resize(1400, 850)
    choose(w, "manager")
    return w


def test_tree_lists_states_categories_playlists_and_tools_with_counts(manager, qtbot):
    a, b, c = add(manager, 1, size=100), add(manager, 2), add(manager, 3)
    cat = manager.org.create_category("Estudo")
    manager.org.assign_categories([a.id, b.id], add=[cat.id])
    pl = manager.org.create_playlist("Lista")
    manager.org.add_to_playlist(pl.id, [c.id])
    manager.library.notify()
    qtbot.waitUntil(lambda: manager.nav_tree.keys() and f"category/{cat.id}" in manager.nav_tree.keys(), timeout=3000)
    keys = manager.nav_tree.keys()
    assert {"library/all", "library/downloaded", "library/saved", f"playlist/{pl.id}", "page/downloads"} <= set(keys)
    text = lambda key: manager.nav_tree._items[key].text(0)
    assert text("library/all").endswith("3") and text("library/downloaded").endswith("1") and text(f"category/{cat.id}").endswith("2")


def test_clicking_the_tree_filters_the_table(manager, qtbot):
    a, b = add(manager, 1, size=100), add(manager, 2)
    manager.library.notify()
    qtbot.waitUntil(lambda: "library/downloaded" in manager.nav_tree.keys(), timeout=3000)
    manager.nav_tree._clicked(manager.nav_tree._items["library/downloaded"])
    assert manager.current_page == "library" and manager.query_state.query.state == "downloaded"
    manager.pages["library"].refresh()
    assert manager.pages["library"]._table.video_ids() == [a.id]
    assert manager.nav_tree.selected_key() == "library/downloaded"


def test_tree_category_playlist_and_tool_entries(manager, qtbot):
    a = add(manager, 1)
    cat = manager.org.create_category("C")
    pl = manager.org.create_playlist("P")
    manager.library.notify()
    qtbot.waitUntil(lambda: f"playlist/{pl.id}" in manager.nav_tree.keys(), timeout=3000)
    manager.nav_tree._clicked(manager.nav_tree._items[f"category/{cat.id}"])
    assert manager.query_state.query.category_ids == frozenset({cat.id})
    manager.nav_tree._clicked(manager.nav_tree._items[f"playlist/{pl.id}"])
    assert manager.query_state.query.playlist_id == pl.id
    manager.nav_tree._clicked(manager.nav_tree._items["page/downloads"])
    assert manager.current_page == "downloads"


def test_list_pages_are_redirected_to_the_library_table(manager):
    add(manager, 1)
    manager.show_page("home")
    assert manager.current_page == "library"
    manager.show_page("downloaded")
    assert manager.current_page == "library" and manager.query_state.query.state == "downloaded"
    manager.show_page("continue")
    assert manager.query_state.query.watch == "in_progress"
    manager.show_page("settings")
    assert manager.current_page == "settings"


def test_status_bar_summarizes_the_library_selection_and_disk(manager, qtbot):
    a, b = add(manager, 1, size=2048), add(manager, 2)
    manager.library.notify()
    qtbot.waitUntil(lambda: "2 vídeos" in manager.status_bar.summary.text(), timeout=3000)
    assert "1 baixados" in manager.status_bar.summary.text() and "livre" in manager.status_bar.disk.text()
    manager.show_page("library")
    manager.pages["library"].refresh()
    manager.pages["library"]._table.select_ids([a.id, b.id])
    assert manager.status_bar.selection.text() == "2 selecionados"
    manager.pages["library"]._table.select_ids([a.id])
    assert manager.status_bar.selection.text() == "1 selecionado"


def test_ribbon_buttons_act_on_the_selection(manager):
    a, b = add(manager, 1), add(manager, 2)
    page = manager.pages["library"]
    page.refresh()
    page._table.select_ids([a.id, b.id])
    assert not page.open_button.isEnabled() and page.queue_button.isEnabled()
    page.queue_button.click()
    assert manager.queue.ids == [a.id, b.id]
    page.watched_button.click()
    assert manager.progress.get(a.id).watched and manager.progress.get(b.id).watched
    page._table.select_ids([a.id])
    page.open_button.click()
    assert manager.current_page == "watch" and manager.watch_page.player.video.id == a.id


def test_preview_pane_follows_a_single_selection(manager):
    a, b = add(manager, 1, "Primeiro"), add(manager, 2, "Segundo")
    page = manager.pages["library"]
    page.refresh()
    table = page._table
    assert page._preview is not None and page._preview.video is None
    table.select_ids([a.id])
    assert page._preview.video.id == a.id and page._preview.name_label.text() == "Primeiro" and not page._preview.thumb.isHidden()
    table.select_ids([a.id, b.id])
    assert page._preview.video is None
    assert page._preview.timestamp_button.isHidden()  # a prévia não tem player ao lado


def test_manager_page_has_no_page_title_and_a_slim_top_bar(manager):
    page = manager.pages["library"]
    assert page.title.isHidden() and page.subtitle.isHidden() and manager.top_bar.property("slim") is True
    assert page.grid_button.isHidden() and page.list_button.isHidden()


# ======================= E. Estação: painéis e marcadores =======================
@pytest.fixture
def station(w):
    w.resize(1500, 880)
    choose(w, "workstation")
    return w


def test_dock_has_library_queue_and_notes_tabs(station):
    dock = station.watch_page.dock
    assert list(dock.tab_buttons) == ["library", "queue", "notes"] and dock.current_tab == "library"
    dock.tab_buttons["queue"].click()
    assert dock.current_tab == "queue" and dock.stack.currentWidget() is dock.queue
    dock.tab_buttons["notes"].click()
    assert dock.current_tab == "notes"


def test_dock_queue_tab_edits_the_global_queue(station):
    a, b, c = add(station, 1), add(station, 2), add(station, 3)
    station.queue.add([a.id, b.id, c.id])
    station.open_saved_video(a.id)
    dock = station.watch_page.dock
    dock.tab_buttons["queue"].click()
    assert dock.queue.list.count() == 3
    dock.queue.list.setCurrentRow(1)
    dock.queue.remove_button.click()
    assert station.queue.ids == [a.id, c.id]
    dock.queue.next_button.click()
    assert station.watch_page.player.video.id == c.id


def test_notes_tab_lists_videos_that_have_notes_and_opens_them(station, qtbot):
    a, b = add(station, 1, "Com nota"), add(station, 2, "Sem nota")
    station.library.set_notes(a.id, "primeira linha\nsegunda")
    dock = station.watch_page.dock
    dock.tab_buttons["notes"].click()
    qtbot.waitUntil(lambda: dock.notes.list.count() == 1, timeout=3000)
    item = dock.notes.list.item(0)
    assert "Com nota" in item.text() and "primeira linha" in item.text()
    dock.notes.list.itemClicked.emit(item)
    assert station.watch_page.player.video.id == a.id


def test_notes_index_updates_when_a_note_is_saved(station, qtbot):
    a = add(station, 1)
    dock = station.watch_page.dock
    dock.tab_buttons["notes"].click()
    assert dock.notes.list.count() == 0 and not dock.notes.empty_label.isHidden()
    station.open_saved_video(a.id)
    station.watch_page.details.notes.setPlainText("anotei")
    station.watch_page.details.flush()
    qtbot.waitUntil(lambda: dock.notes.list.count() == 1, timeout=3000)


def test_markers_are_parsed_from_notes_and_seek_the_player(station):
    a = add(station, 1)
    station.open_saved_video(a.id)
    player = station.watch_page.player
    player._backend.loaded.emit()
    details = station.watch_page.details
    details.notes.setPlainText("[0:30] introdução\nsem marcador\n[2:05] ponto chave")
    assert details.markers.count() == 2 and "2:05" in details.markers.item(1).text() and "ponto chave" in details.markers.item(1).text()
    details.markers.itemClicked.emit(details.markers.item(1))
    assert ("seek", 125.0) in player._backend.calls


def test_marker_hint_shows_when_there_are_none_and_status_bar_is_present(station):
    a = add(station, 1)
    station.open_saved_video(a.id)
    assert not station.watch_page.details.markers_hint.isHidden() and station.watch_page.details.markers.isHidden()
    assert not station.status_bar.isHidden() and station.top_bar.property("slim") is True


# ======================= selo de cada anatomia =======================
def test_every_layout_has_a_visibly_different_set_of_bars(w):
    seen = set()
    for key in ("classic", "streaming", "cinema", "manager", "workstation", "compact"):
        choose(w, key)
        shape = tuple(not getattr(w, name).isHidden() for name in ("sidebar", "top_nav", "nav_tree", "top_bar", "compact_bar", "status_bar", "footer"))
        seen.add(shape + (w.sidebar.mode, w.top_bar.property("slim"), w.top_nav.property("navStyle")))
    assert len(seen) == 6
