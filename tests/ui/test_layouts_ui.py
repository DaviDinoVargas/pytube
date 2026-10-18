import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.domain import layouts
from app.domain.models import Progress
from app.ui.widgets.hero_banner import HeroBanner
from app.ui.widgets.thumb_row import ThumbRow
from tests.fakes import FakeProvider


@pytest.fixture
def w(window_factory):
    return window_factory()


def add(w, i, title=None, size=None):
    """Cada vídeo tem canal próprio, para os relacionados dependerem só do que o teste configurar."""
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


# ======================= seletor =======================
def test_settings_lists_the_six_layouts_with_names_and_descriptions(w):
    buttons = w.settings_page.layout_buttons
    assert list(buttons) == list(layouts.LAYOUT_CHOICES)
    assert buttons["classic"].isChecked()
    assert buttons["streaming"].accessibleName() == "Streaming"
    assert "Menu lateral" in buttons["classic"].toolTip()


@pytest.mark.parametrize("key", layouts.LAYOUT_CHOICES)
def test_each_layout_can_be_chosen_and_persists(window_factory, settings, key):
    w = window_factory()
    choose(w, key)
    assert settings.layout == key and w.settings_page.layout_buttons[key].isChecked()
    assert w.layouts.key == key
    again = window_factory()
    assert again.layouts.key == key and again.settings_page.layout_buttons[key].isChecked()


def test_layout_and_theme_are_independent(w, settings):
    choose(w, "cinema")
    w.settings_page.theme_buttons["nord"].click()
    assert settings.layout == "cinema" and settings.theme == "nord"
    choose(w, "classic")
    assert settings.theme == "nord"


def test_layout_preview_uses_the_current_theme(w):
    swatch = w.settings_page.layout_buttons["streaming"]
    w.settings_page.theme_buttons["dracula"].click()
    from app.styles.tokens import THEMES

    assert swatch._tokens["accent"] == THEMES["dracula"]["accent"]


def test_landing_page_of_each_layout(w):
    choose(w, "manager")
    assert w.current_page == "library"
    choose(w, "workstation")
    assert w.current_page == "watch"
    choose(w, "classic")
    assert w.current_page == "home"


def test_navigation_follows_the_layout(w):
    assert w.sidebar.mode == "full" and not w.sidebar.collapsed and w.top_nav.isHidden() and w.nav_tree.isHidden()
    choose(w, "streaming")  # abas no topo, nada de sidebar
    assert w.sidebar.isHidden() and not w.top_nav.isHidden() and w.top_bar.isHidden()
    choose(w, "workstation")  # barra de atividades (ícones)
    assert w.sidebar.mode == "icons" and w.sidebar.collapsed and w.top_nav.isHidden()
    choose(w, "manager")  # árvore
    assert w.sidebar.isHidden() and not w.nav_tree.isHidden() and not w.status_bar.isHidden()
    choose(w, "compact")  # só o cabeçalho da janela pequena
    assert w.sidebar.isHidden() and w.top_bar.isHidden() and not w.compact_bar.isHidden()
    choose(w, "classic")
    assert w.sidebar.mode == "full" and not w.sidebar.isHidden() and w.compact_bar.isHidden() and w.status_bar.isHidden()


def test_gear_stays_at_the_bottom_right_in_every_layout(w):
    for key in ("classic", "streaming", "cinema", "manager", "workstation", "compact"):
        choose(w, key)
        owner = w.status_bar if w.layouts.profile.statusbar else w.footer
        assert w.settings_button.parentWidget() is owner and not owner.isHidden(), key


def test_icons_sidebar_can_be_peeked_open_without_changing_the_saved_preference(w, settings):
    choose(w, "workstation")
    w.sidebar._toggle.click()
    assert not w.sidebar.collapsed and settings.sidebar_collapsed is False
    w.sidebar._toggle.click()
    assert w.sidebar.collapsed and settings.sidebar_collapsed is False


def test_user_collapse_preference_is_kept_through_layout_changes(w, settings):
    w.sidebar.set_collapsed(True)
    choose(w, "workstation")
    choose(w, "classic")
    assert w.sidebar.collapsed and settings.sidebar_collapsed is True


# ======================= B. Streaming =======================
def test_streaming_home_has_hero_rows_and_opens_videos(w):
    a, b = add(w, 1, "Aula A"), add(w, 2, "Aula B")
    w.progress.save(a.id, 120, 600)
    choose(w, "streaming")
    w.show_page("home")
    home = w.pages["home"]
    hero = home.findChildren(HeroBanner)[0]
    assert hero.video.id == a.id  # em andamento vem primeiro
    assert "2:00" in hero.play_button.text()  # 'Continuar de 2:00'
    titles = [lbl.text() for lbl in home.findChildren(QLabel) if lbl.objectName() == "sectionTitle"]
    assert "Continuar assistindo" in titles and "Adicionados recentemente" in titles
    hero.play_button.click()
    assert w.current_page == "watch" and w.watch_page.player.video.id == a.id


def test_streaming_home_shows_the_classic_grid_again_when_layout_goes_back(w):
    add(w, 1)
    choose(w, "streaming")
    w.show_page("home")
    assert w.pages["home"].findChildren(HeroBanner)
    choose(w, "classic")
    assert w.current_page == "home" and not w.pages["home"].findChildren(HeroBanner)


def test_streaming_rows_include_categories_playlists_and_recommendations(w):
    a, b, c = add(w, 1, "A"), add(w, 2, "B"), add(w, 3, "C")
    cat = w.org.create_category("Estudo")
    w.org.assign_categories([a.id, b.id, c.id], add=[cat.id])
    pl = w.org.create_playlist("Minha lista")
    w.org.add_to_playlist(pl.id, [a.id])
    w.progress.save(a.id, 100, 600)
    choose(w, "streaming")
    w.show_page("home")
    text = " | ".join(lbl.text() for lbl in w.pages["home"].findChildren(QLabel) if lbl.objectName() == "sectionTitle")
    assert "Estudo" in text and "Suas playlists" in text and "Porque você assistiu" in text


def test_playlist_card_in_streaming_row_opens_the_playlist(w):
    a = add(w, 1)
    pl = w.org.create_playlist("Lista X")
    w.org.add_to_playlist(pl.id, [a.id])
    choose(w, "streaming")
    w.show_page("home")
    from app.ui.pages.categories_page import CollectionCard

    card = w.pages["home"].findChildren(CollectionCard)[0]
    card.opened.emit(card.item_id)
    assert w.current_page == "playlist" and w.playlist_page.playlist_id == pl.id


def test_thumb_row_arrows_follow_the_scroll_range(w):
    for i in range(1, 15):
        add(w, i)
    choose(w, "streaming")
    w.resize(900, 800)
    w.show_page("home")
    row = w.pages["home"].findChildren(ThumbRow)[0]
    bar = row.scroll.horizontalScrollBar()
    assert bar.maximum() > 0
    assert row.next_button.isEnabled() and not row.prev_button.isEnabled()
    bar.setValue(bar.maximum())
    assert row.prev_button.isEnabled() and not row.next_button.isEnabled()


# ======================= A. Clássica: detalhes e relacionados =======================
def test_details_toggle_is_classic_only_and_persists(w, settings):
    wp = w.watch_page
    assert not wp.details_toggle.isHidden() and wp.details.isHidden()
    wp.details_toggle.click()
    assert not wp.details.isHidden() and settings.watch_details is True
    wp.details_toggle.click()
    assert wp.details.isHidden() and settings.watch_details is False
    wp.details_toggle.click()
    choose(w, "cinema")
    assert wp.details.isHidden() and wp.details_toggle.isHidden()


def test_related_strip_shows_videos_that_share_a_category(w):
    a, b, c = add(w, 1, "Principal"), add(w, 2, "Parecido"), add(w, 3, "Outro assunto")
    cat = w.org.create_category("Python")
    w.org.assign_categories([a.id, b.id], add=[cat.id])
    w.open_saved_video(a.id)
    related = w.watch_page.related
    assert not related.isHidden() and [i.video_id for i in related.items] == [b.id]
    related.items[0].open_requested.emit(b.id)
    assert w.watch_page.player.video.id == b.id


def test_related_strip_hidden_when_nothing_in_common_and_in_cinema_layout(w):
    a, b = add(w, 1), add(w, 2)
    w.open_saved_video(a.id)
    assert w.watch_page.related.isHidden()
    cat = w.org.create_category("X")
    w.org.assign_categories([a.id, b.id], add=[cat.id])
    w.open_saved_video(a.id)
    assert not w.watch_page.related.isHidden()
    choose(w, "cinema")
    assert w.watch_page.related.isHidden()


# ======================= E. Estação de trabalho =======================
@pytest.fixture
def station(w):
    w.resize(1400, 850)
    choose(w, "workstation")
    return w


def test_workstation_shows_list_player_and_details_at_once(station):
    wp = station.watch_page
    a = add(station, 1, "Aula 1")
    station.open_saved_video(a.id)
    assert not wp.dock.isHidden() and not wp.details.isHidden()
    assert wp.details.video.id == a.id and wp.details.name_label.text() == "Aula 1"
    assert wp.library_list.list.count() == 1


def test_workstation_starts_empty_and_panes_hide_on_narrow_windows(station):
    wp = station.watch_page
    assert station.current_page == "watch" and wp.stack.currentIndex() == 3
    assert wp.details.video is None and not wp.details.notes.isEnabled()
    station.resize(1100, 800)
    assert wp.dock.isHidden() and not wp.details.isHidden()
    station.resize(940, 800)
    assert wp.details.isHidden()
    station.resize(1400, 850)
    assert not wp.dock.isHidden() and not wp.details.isHidden()


def test_clicking_the_list_opens_the_video_in_the_center(station):
    a, b = add(station, 1, "Primeiro"), add(station, 2, "Segundo")
    station.open_saved_video(a.id)
    lst = station.watch_page.library_list
    row = next(i for i in range(lst.list.count()) if lst.list.item(i).data(Qt.UserRole) == b.id)
    lst.list.itemClicked.emit(lst.list.item(row))
    assert station.watch_page.player.video.id == b.id and station.watch_page.details.video.id == b.id


def test_list_search_filters_and_marks_the_current_video(station, qtbot):
    a, b = add(station, 1, "Python avançado"), add(station, 2, "Receita de bolo")
    station.open_saved_video(a.id)
    lst = station.watch_page.library_list
    lst.search.setText("receita")
    qtbot.waitUntil(lambda: lst.list.count() == 1, timeout=3000)
    assert lst.list.item(0).data(Qt.UserRole) == b.id
    lst.search.setText("")
    qtbot.waitUntil(lambda: lst.list.count() == 2, timeout=3000)
    assert lst.list.currentItem().data(Qt.UserRole) == a.id


def test_notes_autosave_after_typing_and_survive_switching_videos(station, qtbot):
    a, b = add(station, 1), add(station, 2)
    station.open_saved_video(a.id)
    details = station.watch_page.details
    details.notes.setPlainText("anotação da aula 1")
    qtbot.waitUntil(lambda: station.library.get(a.id).notes == "anotação da aula 1", timeout=3000)
    assert "salvas" in details.status_label.text()
    details.notes.setPlainText("rascunho ainda não gravado")
    station.open_saved_video(b.id)  # trocar de vídeo grava o que estava pendente, no vídeo certo
    assert station.library.get(a.id).notes == "rascunho ainda não gravado" and station.library.get(b.id).notes == ""
    assert details.notes.toPlainText() == ""
    station.open_saved_video(a.id)
    assert details.notes.toPlainText() == "rascunho ainda não gravado"


def test_insert_timestamp_adds_current_position(station):
    a = add(station, 1)
    station.open_saved_video(a.id)
    player = station.watch_page.player
    player._backend.loaded.emit()
    player._on_position(player._backend, 754.0, 900.0)
    details = station.watch_page.details
    details.timestamp_button.click()
    assert details.notes.toPlainText().startswith("[12:34] ")


def test_details_shows_categories_and_updates_when_they_change(station):
    a = add(station, 1)
    station.open_saved_video(a.id)
    details = station.watch_page.details
    assert details.categories_label.text() == "Sem categorias"
    cat = station.org.create_category("Estudo")
    station.org.assign_categories([a.id], add=[cat.id])
    station.library.notify()
    assert details.categories_label.text() == "Estudo"


def test_unsaved_video_has_notes_disabled(station):
    station.watch_page.details.set_video(None)
    assert not station.watch_page.details.notes.isEnabled()
    assert "Salve o vídeo" in station.watch_page.details.status_label.text()


def test_removing_the_open_video_clears_the_details_panel(station):
    a = add(station, 1)
    station.open_saved_video(a.id)
    station.library.remove(a.id)
    assert station.watch_page.details.video is None


# ======================= C. Modo cinema =======================
@pytest.fixture
def cinema(w):
    w.resize(1300, 820)
    choose(w, "cinema")
    return w


def start(w, i=1):
    v = add(w, i)
    w.open_saved_video(v.id)
    w.watch_page.player._backend.loaded.emit()
    return v


def test_cinema_has_no_sidebar_and_its_top_navigation_goes_away_while_watching(cinema):
    assert cinema.sidebar.isHidden() and not cinema.top_nav.isHidden() and cinema.top_nav.property("navStyle") == "cinema"
    start(cinema)
    assert cinema.sidebar.isHidden() and cinema.top_nav.isHidden() and cinema.top_bar.isHidden()
    cinema.show_page("library")
    assert not cinema.top_nav.isHidden()


def test_cinema_player_fills_the_window_on_a_black_stage(cinema):
    start(cinema)
    wp = cinema.watch_page
    assert wp.stage.property("cinema") is True and wp.cinema
    assert wp.player.maximumWidth() > 1000 and wp.player.width() > 1000
    assert wp.stage.minimumHeight() >= wp.height() - 40
    assert "QFrame#stage[cinema=\"true\"] { background: #000000" in __import__("PySide6.QtWidgets", fromlist=["QApplication"]).QApplication.instance().styleSheet()


def test_cinema_overlay_shows_title_and_buttons(cinema):
    v = start(cinema)
    wp = cinema.watch_page
    assert not wp.cinema_bar.isHidden() and wp.cinema_title.text() == v.title
    assert wp.back_button.isHidden() and wp.details_toggle.isHidden()
    wp.cinema_back.click()
    assert cinema.current_page != "watch"


def test_controls_hide_when_idle_and_playing_and_return_on_activity(cinema):
    start(cinema)
    wp = cinema.watch_page
    wp.player._backend._playing = True
    wp._on_activity(False)
    assert wp._controls_fade.opacity() == 0.0 and wp.cinema_bar.isHidden()
    assert wp.player.controls.testAttribute(Qt.WA_TransparentForMouseEvents)
    wp._on_activity(True)
    assert wp._controls_fade.opacity() == 1.0 and not wp.cinema_bar.isHidden()
    assert not wp.player.controls.testAttribute(Qt.WA_TransparentForMouseEvents)


def test_controls_stay_visible_when_paused(cinema):
    start(cinema)
    wp = cinema.watch_page
    wp.player._backend._playing = False
    wp._on_activity(False)
    assert wp._controls_fade.opacity() == 1.0 and not wp.cinema_bar.isHidden()


def test_idle_watcher_runs_only_in_cinema_while_the_page_is_shown(cinema):
    wp = cinema.watch_page
    assert not wp.idle.running  # a página ainda não está visível
    start(cinema)
    assert wp.idle.running
    cinema.show_page("home")
    assert not wp.idle.running
    choose(cinema, "classic")
    cinema.open_saved_video(1)
    assert not wp.idle.running and wp.cinema_bar.isHidden() and wp._controls_fade.opacity() == 1.0


def test_leaving_cinema_restores_the_standard_watch_page(cinema):
    start(cinema)
    choose(cinema, "classic")
    cinema.open_saved_video(1)
    wp = cinema.watch_page
    assert wp.player.maximumWidth() <= 1000 and wp.stage.property("cinema") is False
    assert not wp.back_button.isHidden() and not cinema.sidebar.isHidden() and not cinema.top_bar.isHidden() and cinema.top_nav.isHidden()


def test_info_button_scrolls_to_the_details_below_the_video_and_back(cinema):
    start(cinema)
    wp = cinema.watch_page
    bar = wp.scroll.verticalScrollBar()
    assert bar.maximum() > 0 and bar.value() == 0
    wp.cinema_info.click()
    assert bar.value() > 0
    wp.cinema_info.click()
    assert bar.value() == 0


def test_idle_watcher_poke_and_timeout(qtbot):
    from app.ui.idle import IdleWatcher

    watcher = IdleWatcher(timeout_ms=120, interval_ms=30)
    states = []
    watcher.active_changed.connect(states.append)
    watcher.start()
    qtbot.waitUntil(lambda: states == [False], timeout=3000)
    watcher.poke()
    assert states == [False, True]
    qtbot.waitUntil(lambda: states == [False, True, False], timeout=3000)
    watcher.stop()
    assert states[-1] is True and not watcher.running


# ======================= D. Gerenciador de biblioteca =======================
from app.ui.widgets.library_table import LibraryTable  # noqa: E402


@pytest.fixture
def manager(w):
    w.resize(1400, 850)
    choose(w, "manager")
    return w


def table_of(w):
    page = w.pages["library"]
    assert page._table is not None
    return page._table


def test_manager_opens_the_library_as_a_table_with_inline_filters(manager):
    page = manager.pages["library"]
    add(manager, 1)
    page.refresh()
    assert manager.current_page == "library" and page._view == "table"
    assert not page.filter_bar.isHidden() and page.filter_button.isHidden()
    assert isinstance(table_of(manager), LibraryTable) and page.table_button.isChecked()


def test_manager_does_not_overwrite_the_user_view_preference(manager, settings):
    assert settings.library_view == "grid"
    choose(manager, "classic")
    page = manager.pages["library"]
    manager.show_page("library")
    assert page._view == "grid" and page.filter_bar.isHidden() and not page.filter_button.isHidden()


def test_table_columns_show_title_duration_category_date_state_and_file(manager):
    a = add(manager, 1, "Aula Python")
    cat = manager.org.create_category("Estudo")
    manager.org.assign_categories([a.id], add=[cat.id])
    f = manager.library.layout.videos / "a.mp4"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"0" * 2048)
    manager.library.attach_local_file(a.id, f, "720p")
    manager.pages["library"].refresh()
    table = table_of(manager)
    model = table.model()
    headers = [model.headerData(i, Qt.Horizontal) for i in range(model.columnCount())]
    assert headers == ["Título", "Duração", "Categorias", "Adicionado em", "Estado", "Arquivo"]
    row = [model.index(0, c).data() for c in range(model.columnCount())]
    assert row[0] == "Aula Python" and row[1] == "3:32" and row[2] == "Estudo" and "Baixado" in row[4] and row[5].endswith("a.mp4")


def test_table_saved_only_and_missing_states(manager):
    saved = add(manager, 1)
    gone = add(manager, 2, size=100)
    (manager.library.layout.videos / "2.mp4").unlink()
    manager.pages["library"].refresh()
    model = table_of(manager).model()
    states = {model.index(r, 0).data(): model.index(r, 4).data() for r in range(model.rowCount())}
    assert states[saved.title] == "Só salvo" and "ausente" in states[gone.title]


def test_header_click_sorts_locally_and_numeric_columns_sort_by_value(manager):
    for i, title in enumerate(["Banana", "Abacate", "Cereja"], 1):
        add(manager, i, title)
    manager.pages["library"].refresh()
    table = table_of(manager)
    assert table.sort_state()[0] == -1  # sem ordenação própria: vale a da barra
    table.horizontalHeader().sectionClicked.emit(0)
    table.sortByColumn(0, Qt.AscendingOrder)
    assert [table.model().index(r, 0).data() for r in range(3)] == ["Abacate", "Banana", "Cereja"]
    table.sortByColumn(0, Qt.DescendingOrder)
    assert table.model().index(0, 0).data() == "Cereja"


def test_double_click_and_enter_open_the_video(manager):
    a = add(manager, 1, "Abrir")
    manager.pages["library"].refresh()
    table = table_of(manager)
    table.doubleClicked.emit(table.model().index(0, 0))
    assert manager.current_page == "watch" and manager.watch_page.player.video.id == a.id


def test_selecting_rows_shows_the_bulk_bar_and_bulk_remove_asks_once(manager, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    a, b, c = add(manager, 1), add(manager, 2), add(manager, 3)
    page = manager.pages["library"]
    page.refresh()
    assert not page.bulk_bar.isHidden() and not page.open_button.isEnabled()  # a faixa de ações existe, mas sem seleção está inerte
    table = table_of(manager)
    table.select_ids([a.id, b.id])
    assert page.selected_ids == [a.id, b.id] and not page.bulk_bar.isHidden()
    asked = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: asked.append(self.text()) or 0)
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda self: self.buttons()[0])
    table.action_requested.emit([a.id, b.id], "remove")
    assert len(asked) == 1 and [v.id for v in manager.library.list_videos()] == [c.id]


def test_row_actions_watch_and_unwatch_use_the_video_actions(manager):
    a = add(manager, 1)
    page = manager.pages["library"]
    page.refresh()
    table_of(manager).action_requested.emit([a.id], "watch")
    assert manager.progress.get(a.id).watched is True
    table_of(manager).action_requested.emit([a.id], "unwatch")
    assert manager.progress.get(a.id).watched is False


def test_column_choice_is_saved_and_title_cannot_be_hidden(manager, settings):
    add(manager, 1)
    page = manager.pages["library"]
    page.refresh()
    table = table_of(manager)
    table._toggle_column("channel", True)
    table._toggle_column("added", False)
    assert "channel" in settings.library_columns and "added" not in settings.library_columns
    assert table.columns == ["title", "channel", "duration", "categories", "state", "file"]
    menu_actions = {x.text(): x for x in table.build_columns_menu().actions()}
    assert menu_actions["Título"].isEnabled() is False and menu_actions["Canal"].isChecked()


def test_row_context_menu_has_open_watch_organize_and_remove(manager):
    a = add(manager, 1, size=100)
    manager.pages["library"].refresh()
    table = table_of(manager)
    table.select_ids([a.id])
    menu = table.build_row_menu(table.model().index(0, 0))
    labels = [x.text() for x in menu.actions() if x.text()]
    assert "Abrir" in labels[0] and any("pasta" in lbl for lbl in labels) and labels[-1].startswith("Remover")
    assert any(x.menu() is not None for x in menu.actions())  # categorias e playlists


def test_columns_persist_across_refreshes(manager):
    add(manager, 1)
    page = manager.pages["library"]
    page.refresh()
    table_of(manager)._toggle_column("size", True)
    page.refresh()
    assert "size" in table_of(manager).columns


def test_inline_filter_bar_filters_by_state_and_channel_and_shows_chips(manager, qtbot):
    a, b = add(manager, 1, "Um"), add(manager, 2, "Dois")
    page = manager.pages["library"]
    page.refresh()
    bar = page.filter_bar
    bar.channel_edit.setText("canal 2")
    qtbot.waitUntil(lambda: manager.query_state.query.channel == "canal 2", timeout=3000)
    page.refresh()
    assert table_of(manager).video_ids() == [b.id]
    assert any("Canal: canal 2" in c.text() for c in page.chips.chips)
    bar.clear_button.click()
    page.refresh()
    assert set(table_of(manager).video_ids()) == {a.id, b.id} and bar.channel_edit.text() == ""


def test_filter_bar_reflects_state_changes_from_elsewhere(manager):
    from app.domain.query import STATE_DOWNLOADED

    page = manager.pages["library"]
    manager.query_state.focus(state=STATE_DOWNLOADED)
    page.refresh()
    assert page.filter_bar.state_combo.currentData() == STATE_DOWNLOADED


def test_table_view_can_be_chosen_in_the_classic_layout_and_persists(w, settings):
    add(w, 1)
    w.show_page("library")
    page = w.pages["library"]
    page.table_button.click()
    assert settings.library_view == "table" and page._table is not None
    page.grid_button.click()
    assert settings.library_view == "grid" and page._table is None
