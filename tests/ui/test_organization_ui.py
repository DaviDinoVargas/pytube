import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from app.domain import query as q
from app.domain.models import Progress
from app.ui.dialogs.name_dialog import NameDialog
from tests.fakes import FakeProvider


@pytest.fixture
def w(window_factory):
    return window_factory()


def add(w, i, title, *, status=None, days=0, duration=300):
    video, _ = w.library.save_info(FakeProvider("f", title=title).fetch_info(f"vid{i:08d}"))
    video.duration = duration
    w.library.store.update_video(video)
    if status == "ok":
        f = w.library.layout.videos / f"{i}.mp4"
        f.write_bytes(b"0" * 100)
        w.library.attach_local_file(video.id, f, "720p")
    return w.library.get(video.id)


def seed(w):
    return [add(w, 1, "Alfa python", status="ok"), add(w, 2, "Beta música", duration=100), add(w, 3, "Gama estudos", duration=2000)]


def titles(page):
    items = page.items()
    return [i.video.title for i in items]


def fill_dialog(monkeypatch, name, description="", color=None):
    """Substitui o diálogo modal por um preenchimento automático (o diálogo real é testado à parte)."""

    def fake_exec(self):
        self.name_input.setText(name)
        self.description_input.setText(description)
        if self.swatches and color:
            self._pick(color)
        self._save()
        return self.result()

    monkeypatch.setattr(NameDialog, "exec", fake_exec)


# ======================= biblioteca: busca, filtros, ordenação =======================
def test_library_lists_count_and_default_sort(w):
    seed(w)
    w.show_page("library")
    page = w.pages["library"]
    assert page.count_label.text() == "3 vídeos" and page.sort_combo.currentData() == "newest"
    assert titles(page) == ["Gama estudos", "Beta música", "Alfa python"]


def test_sort_is_applied_and_remembered(w, settings):
    seed(w)
    w.show_page("library")
    page = w.pages["library"]
    page.sort_combo.setCurrentIndex(page.sort_combo.findData("title_az"))
    page.sort_combo.activated.emit(page.sort_combo.currentIndex())
    assert titles(page) == ["Alfa python", "Beta música", "Gama estudos"] and settings.library_sort == "title_az"
    w.close()


def test_sort_preference_survives_restart(window_factory, settings):
    window = window_factory()
    window.query_state.set_sort("oldest")
    assert settings.library_sort == "oldest"
    again = window_factory()
    assert again.query_state.query.sort == "oldest"


def test_search_from_top_bar_filters_library_with_debounce(w, qtbot):
    seed(w)
    w.show_page("home")
    w.top_bar.search_input.setText("musica")  # sem acento casa com "música"
    qtbot.waitUntil(lambda: w.current_page == "library", timeout=3000)
    page = w.pages["library"]
    assert titles(page) == ["Beta música"] and page.count_label.text() == "1 vídeo"
    assert [c.text() for c in page.chips.chips][0].startswith("Busca: “musica”")


def test_no_results_state_offers_to_clear(w, qtbot):
    seed(w)
    w.top_bar.search_input.setText("zzzz")
    qtbot.waitUntil(lambda: w.current_page == "library", timeout=3000)
    page = w.pages["library"]
    assert page.no_results.isVisible() and not page.empty.isVisible() and page.items() == []
    assert "Nenhum vídeo corresponde" in page.no_results.message.text()
    page.no_results_clear.click()
    assert w.top_bar.search_input.text() == "" and len(page.items()) == 3 and not page.no_results.isVisible()


def test_empty_library_state_is_different_from_no_results(w):
    w.show_page("library")
    page = w.pages["library"]
    assert page.empty.isVisible() and not page.no_results.isVisible()


def test_filter_panel_applies_state_filter_and_shows_removable_chip(w):
    seed(w)
    w.show_page("library")
    page = w.pages["library"]
    panel = page.panel
    panel.state_combo.setCurrentIndex(panel.state_combo.findData("downloaded"))
    panel._emit()
    assert titles(page) == ["Alfa python"]
    assert [c.text() for c in page.chips.chips][0].startswith("Baixados") and page.filter_button.text() == "Filtros  (1)"
    page.chips.chips[0].click()
    assert len(page.items()) == 3 and page.filter_button.text() == "Filtros"


def test_combined_filters_and_clear(w):
    seed(w)
    w.show_page("library")
    page = w.pages["library"]
    w.query_state.set_query(q.LibraryQuery(state="saved", duration="long"))
    assert titles(page) == ["Gama estudos"]
    w.query_state.set_query(q.LibraryQuery(state="saved", duration="short"))
    assert titles(page) == ["Beta música"]
    page.chips.chips[-1].click()  # "Limpar filtros"
    assert len(page.items()) == 3


def test_category_chip_and_playlist_filter_keep_order(w):
    videos = seed(w)
    cat = w.org.create_category("Estudos", color="#8B7CF6")
    w.org.assign_categories([videos[0].id, videos[2].id], add=[cat.id])
    pl = w.org.create_playlist("Fila")
    w.org.add_to_playlist(pl.id, [videos[2].id, videos[1].id])
    w.show_library_with(category_ids=frozenset({cat.id}))
    page = w.pages["library"]
    assert set(titles(page)) == {"Alfa python", "Gama estudos"} and page.chips.chips[0].text().startswith("Estudos")
    w.show_library_with(playlist_id=pl.id)
    assert titles(page) == ["Gama estudos", "Beta música"]  # ordem da playlist


def test_progress_filter_uses_saved_playback(w):
    videos = seed(w)
    w.library.store.save_progress(Progress(videos[1].id, position=60, duration=100))
    w.query_state.set_query(q.LibraryQuery(watch="in_progress"))
    w.show_page("library")
    assert titles(w.pages["library"]) == ["Beta música"]


def test_filter_panel_lists_categories_and_playlists(w):
    cat = w.org.create_category("Estudos")
    pl = w.org.create_playlist("Fila")
    w.show_page("library")
    panel = w.pages["library"].panel
    assert list(panel._category_checks) == [cat.id] and panel.playlist_combo.findData(pl.id) >= 0
    panel._category_checks[cat.id].setChecked(True)
    assert w.query_state.query.category_ids == frozenset({cat.id})


# ======================= grade, lista e seleção =======================
def test_list_view_shows_rows_with_categories_and_persists(w, settings):
    videos = seed(w)
    cat = w.org.create_category("Estudos", color="#8B7CF6")
    w.org.assign_categories([videos[0].id], add=[cat.id])
    w.show_page("library")
    page = w.pages["library"]
    page.list_button.click()
    assert len(page.rows()) == 3 and page.cards() == [] and settings.library_view == "list"
    row = next(r for r in page.rows() if r.video.title == "Alfa python")
    assert row.state_label.text() == "Baixado" and [c.text() for c in row.chips] == ["● Estudos"]
    assert row.meta_label.text().startswith("Canal Teste")
    page.grid_button.click()
    assert len(page.cards()) == 3 and page.rows() == []


def test_row_click_opens_video(w, qtbot):
    seed(w)
    w.show_page("library")
    w.pages["library"].list_button.click()
    row = w.pages["library"].rows()[0]
    with qtbot.waitSignal(w.pages["library"].video_opened):
        qtbot.mouseClick(row, Qt.LeftButton)


def test_selection_mode_select_all_and_clicks_toggle_instead_of_opening(w, qtbot):
    seed(w)
    w.show_page("library")
    page = w.pages["library"]
    page.select_button.click()
    assert page.bulk_bar.isVisible() and page.selected_label.text() == "0 selecionados"
    assert not page.remove_button.isEnabled()
    card = page.cards()[0]
    qtbot.mouseClick(card, Qt.LeftButton)
    assert w.current_page == "library" and card.selected and page.selected_label.text() == "1 selecionado"
    page.select_all_button.click()
    assert len(page.selected_ids) == 3 and page.remove_button.isEnabled()
    page.done_button.click()
    assert not page.bulk_bar.isVisible() and page.selected_ids == [] and not any(c.selected for c in page.cards())


def test_bulk_assign_category_and_playlist(w):
    videos = seed(w)
    cat = w.org.create_category("Estudos")
    pl = w.org.create_playlist("Fila")
    w.show_page("library")
    page = w.pages["library"]
    page.select_button.click()
    page.select_all()
    cat_action = next(a for a in page.categories_button.menu().actions() if a.text().startswith("Estudos"))
    cat_action.trigger()
    assert all(w.org.video_category_ids(v.id) == [cat.id] for v in videos)
    page.categories_button.menu().actions()[0].trigger()  # agora todos têm: desmarca
    assert all(w.org.video_category_ids(v.id) == [] for v in videos)
    next(a for a in page.playlist_button.menu().actions() if a.text().startswith("Fila")).trigger()
    assert w.org.playlist_video_ids(pl.id) == [v.id for v in sorted(videos, key=lambda v: -v.id)] or set(w.org.playlist_video_ids(pl.id)) == {v.id for v in videos}


def test_bulk_remove_asks_and_never_deletes_files(w, monkeypatch):
    videos = seed(w)
    w.show_page("library")
    page = w.pages["library"]
    page.select_button.click()
    page.select_all()
    monkeypatch.setattr(type(page), "_confirm_remove", lambda self, count: False)
    page.remove_button.click()
    assert len(w.library.list_videos()) == 3
    monkeypatch.setattr(type(page), "_confirm_remove", lambda self, count: True)
    page.remove_button.click()
    assert w.library.list_videos() == [] and (w.library.layout.videos / "1.mp4").exists()


# ======================= menus do card =======================
def test_card_menu_has_category_and_playlist_submenus_that_work(w, monkeypatch):
    videos = seed(w)
    cat = w.org.create_category("Estudos")
    pl = w.org.create_playlist("Fila")
    w.show_page("library")
    card = next(c for c in w.pages["library"].cards() if c.video.id == videos[0].id)
    assert {"Categorias", "Adicionar à playlist"} <= set(card.action_keys())
    menu = card.menu_button.menu()
    menu.aboutToShow.emit()
    sub = next(a for a in menu.actions() if a.text() == "Categorias").menu()
    next(a for a in sub.actions() if a.text() == "Estudos").trigger()
    assert w.org.video_category_ids(videos[0].id) == [cat.id]
    menu.aboutToShow.emit()
    sub = next(a for a in menu.actions() if a.text() == "Categorias").menu()
    assert next(a for a in sub.actions() if a.text() == "Estudos").isChecked()  # estado atual refletido
    psub = next(a for a in menu.actions() if a.text() == "Adicionar à playlist").menu()
    next(a for a in psub.actions() if a.text().startswith("Fila")).trigger()
    assert w.org.playlist_video_ids(pl.id) == [videos[0].id]


def test_new_category_from_card_menu_creates_and_assigns(w, monkeypatch):
    videos = seed(w)
    w.show_page("library")
    card = w.pages["library"].cards()[0]
    fill_dialog(monkeypatch, "Nova", color="#5B9BFF")
    menu = card.menu_button.menu()
    sub = next(a for a in menu.actions() if a.text() == "Categorias").menu()
    next(a for a in sub.actions() if a.text() == "Nova categoria…").trigger()
    cats = w.org.categories()
    assert [(c.name, c.color) for c in cats] == [("Nova", "#5B9BFF")]
    assert w.org.video_category_ids(card.video.id) == [cats[0].id]


# ======================= páginas de categorias e playlists =======================
def test_categories_page_create_edit_delete_keep_videos(w, monkeypatch):
    videos = seed(w)
    page = w.pages["categories"]
    w.show_page("categories")
    assert page.empty.isVisible()
    fill_dialog(monkeypatch, "Estudos", "para aprender", "#8B7CF6")
    page.new_button.click()
    assert [c.name_label.text() for c in page.cards] == ["Estudos"] and page.cards[0].count_label.text() == "0 vídeos"
    w.org.assign_categories([videos[0].id, videos[1].id], add=[page.cards[0].item_id])
    assert page.cards[0].count_label.text() == "2 vídeos" and page.cards[0].description_label.text() == "para aprender"
    fill_dialog(monkeypatch, "Estudos 2", "", None)
    page._edit(page.cards[0].item_id)
    assert page.cards[0].name_label.text() == "Estudos 2"
    monkeypatch.setattr(type(page), "_confirm", lambda self, *a: True)
    page._delete(page.cards[0].item_id)
    assert page.cards == [] and page.empty.isVisible() and len(w.library.list_videos()) == 3


def test_category_dialog_rejects_duplicates_and_keeps_open(w, monkeypatch):
    w.org.create_category("Estudos")
    seen = {}

    def fake_exec(self):
        self.name_input.setText("estudos")
        self._save()
        seen["error"] = self.error_label.text()
        seen["visible"] = not self.error_label.isHidden()
        return self.result()

    monkeypatch.setattr(NameDialog, "exec", fake_exec)
    assert w._prompt_category() is None
    assert seen["visible"] and "já existe" in seen["error"]
    assert len(w.org.categories()) == 1


def test_clicking_category_opens_library_filtered(w):
    videos = seed(w)
    cat = w.org.create_category("Estudos")
    w.org.assign_categories([videos[2].id], add=[cat.id])
    w.show_page("categories")
    w.pages["categories"].cards[0].opened.emit(cat.id)
    assert w.current_page == "library" and titles(w.pages["library"]) == ["Gama estudos"]


def test_playlists_page_create_rename_delete_keep_videos(w, monkeypatch):
    videos = seed(w)
    page = w.pages["playlists"]
    w.show_page("playlists")
    fill_dialog(monkeypatch, "Fila de hoje")
    page.new_button.click()
    assert [c.name_label.text() for c in page.cards] == ["Fila de hoje"] and page.cards[0].play_button is None  # vazia: sem "reproduzir"
    pid = page.cards[0].item_id
    w.org.add_to_playlist(pid, [v.id for v in videos])
    assert page.cards[0].count_label.text() == "3 vídeos" and page.cards[0].play_button is not None
    fill_dialog(monkeypatch, "Renomeada")
    page._rename(pid)
    assert page.cards[0].name_label.text() == "Renomeada"
    monkeypatch.setattr(type(page), "_confirm", lambda self, *a: True)
    page._delete(pid)
    assert page.cards == [] and len(w.library.list_videos()) == 3 and (w.library.layout.videos / "1.mp4").exists()


def test_playlist_detail_reorders_and_removes(w):
    videos = seed(w)
    pl = w.org.create_playlist("Fila")
    a, b, c = (v.id for v in videos)
    w.org.add_to_playlist(pl.id, [a, b, c])
    w.open_playlist(pl.id)
    page = w.playlist_page
    assert w.current_page == "playlist" and w.sidebar._buttons["playlists"].isChecked()
    assert [r.video.id for r in page.rows] == [a, b, c] and page.title.text() == "Fila"
    assert not page.rows[0].buttons["move_up"].isEnabled() and not page.rows[2].buttons["move_down"].isEnabled()
    page.rows[0].buttons["move_down"].click()
    assert [r.video.id for r in page.rows] == [b, a, c]
    page.rows[2].buttons["move_up"].click()
    assert [r.video.id for r in page.rows] == [b, c, a]
    page.rows[1].buttons["remove"].click()
    assert [r.video.id for r in page.rows] == [b, a] and len(w.library.list_videos()) == 3
    page.back_requested.emit()
    assert w.current_page == "playlists"


def test_empty_playlist_shows_hint(w):
    pl = w.org.create_playlist("Vazia")
    w.open_playlist(pl.id)
    assert w.playlist_page.empty.isVisible() and not w.playlist_page.play_all.isVisible()


# ======================= reprodução sequencial =======================
def test_play_all_follows_playlist_order_and_stops_at_the_end(w):
    videos = seed(w)
    a, b, c = (v.id for v in videos)
    pl = w.org.create_playlist("Fila")
    w.org.add_to_playlist(pl.id, [c, a, b])
    w.play_playlist(pl.id)
    page = w.watch_page
    assert w.current_page == "watch" and page.player.video.id == c
    assert page.playlist_label.isVisible() and "Fila" in page.playlist_label.text() and "1 de 3" in page.playlist_label.text()
    page.player._backend.ended.emit()  # o 1º terminou: vai para o 2º
    assert page.player.video.id == a and "2 de 3" in page.playlist_label.text()
    page.player._backend.ended.emit()
    assert page.player.video.id == b and "3 de 3" in page.playlist_label.text()
    page.player._backend.ended.emit()  # fim da playlist
    assert page.player.video.id == b and not page.playlist_label.isVisible() and w._playlist_id is None


def test_play_from_a_specific_item_and_normal_open_leaves_playlist_mode(w):
    videos = seed(w)
    a, b, c = (v.id for v in videos)
    pl = w.org.create_playlist("Fila")
    w.org.add_to_playlist(pl.id, [a, b, c])
    w.playlist_page.show_playlist(pl.id)
    w.playlist_page.play_requested.emit(pl.id, b)
    assert w.watch_page.player.video.id == b and "2 de 3" in w.watch_page.playlist_label.text()
    w.open_saved_video(c)  # abrir por outro caminho sai do modo playlist
    assert not w.watch_page.playlist_label.isVisible()
    w.watch_page.player._backend.ended.emit()
    assert w.watch_page.player.video.id == c  # não avançou


def test_play_all_on_empty_playlist_does_nothing(w):
    pl = w.org.create_playlist("Vazia")
    w.play_playlist(pl.id)
    assert w.current_page != "watch"


# ======================= início e tela do vídeo =======================
def test_home_shows_category_sections_with_see_all(w):
    videos = seed(w)
    cat = w.org.create_category("Estudos", color="#8B7CF6")
    w.org.create_category("Vazia")
    w.org.assign_categories([videos[0].id, videos[2].id], add=[cat.id])
    w.show_page("home")
    labels = [l for l in w.pages["home"].findChildren(QLabel) if l.objectName() == "sectionTitle"]
    texts = [l.text() for l in labels]
    assert any("Estudos" in t for t in texts) and not any("Vazia" in t for t in texts)  # categoria vazia não aparece
    next(b for b in w.pages["home"].findChildren(type(w.pages["library"].select_all_button)) if b.text() == "Ver tudo").click()
    assert w.current_page == "library" and set(titles(w.pages["library"])) == {"Alfa python", "Gama estudos"}


def test_category_name_with_html_is_shown_literally(w):
    videos = seed(w)
    cat = w.org.create_category("<b>x</b>", color="#8B7CF6")
    w.org.assign_categories([videos[0].id], add=[cat.id])
    w.show_page("home")
    texts = [l.text() for l in w.pages["home"].findChildren(QLabel) if l.objectName() == "sectionTitle"]
    assert any("&lt;b&gt;x&lt;/b&gt;" in t for t in texts)


def test_watch_page_category_and_playlist_menus(w):
    videos = seed(w)
    cat = w.org.create_category("Estudos")
    pl = w.org.create_playlist("Fila")
    page = w.watch_page
    w.open_saved_video(videos[0].id)
    assert page.categories_button.isEnabled() and page.playlists_button.isEnabled()
    menu = page.categories_button.menu()
    menu.aboutToShow.emit()
    next(a for a in menu.actions() if a.text() == "Estudos").trigger()
    assert w.org.video_category_ids(videos[0].id) == [cat.id]
    menu = page.playlists_button.menu()
    menu.aboutToShow.emit()
    next(a for a in menu.actions() if a.text().startswith("Fila")).trigger()
    assert w.org.playlist_video_ids(pl.id) == [videos[0].id]


def test_watch_page_organize_buttons_disabled_until_saved(w, qtbot):
    w.top_bar.url_input.setText("https://youtu.be/dQw4w9WgXcQ")
    w.top_bar.open_button.click()
    qtbot.waitUntil(lambda: w.watch_page.stack.currentIndex() == 2, timeout=10000)
    assert not w.watch_page.categories_button.isEnabled() and not w.watch_page.playlists_button.isEnabled()


def test_language_switch_retranslates_organization_ui(w):
    videos = seed(w)
    w.org.create_category("Estudos")
    w.show_page("library")
    combo = w.settings_page.language_combo
    combo.setCurrentIndex(combo.findData("en"))
    page = w.pages["library"]
    assert page.count_label.text() == "3 videos" and page.select_button.text() == "Select" and page.sort_combo.currentText() == "Newest"
    w.query_state.set_query(q.LibraryQuery(state="downloaded"))
    assert page.chips.chips[0].text().startswith("Downloaded")
    assert w.pages["categories"].new_button.text() == "+  New category"
