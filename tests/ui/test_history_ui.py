import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from app.domain import query as q
from app.domain.models import Progress, now_iso
from tests.fakes import FakeProvider


@pytest.fixture
def w(window_factory):
    return window_factory()


def add(w, i, title):
    video, _ = w.library.save_info(FakeProvider("f", title=title).fetch_info(f"vid{i:08d}"))
    video.duration = 100
    w.library.store.update_video(video)
    return w.library.get(video.id)


def seed(w):
    return [add(w, 1, "Alfa"), add(w, 2, "Beta"), add(w, 3, "Gama"), add(w, 4, "Delta")]


def play(w, video, position, duration=100.0, watched=False, when=None):
    progress = Progress(video.id, position=position, duration=duration, watched=watched, last_played_at=when or now_iso())
    w.library.store.save_progress(progress)
    w.library.notify()


def action(card, label):
    return next(a for a in card.menu_button.menu().actions() if a.text() == label)


# ======================= continuar assistindo =======================
def test_continue_page_lists_only_started_unfinished_videos_most_recent_first(w):
    a, b, c, d = seed(w)
    play(w, a, 40, when="2026-10-10T10:00:00+00:00")
    play(w, b, 60, when="2026-10-16T10:00:00+00:00")
    play(w, c, 3)  # menos de 5 s: não conta como começado
    play(w, d, 0, watched=True)  # terminado
    w.show_page("continue")
    page = w.pages["continue"]
    assert [card.video.title for card in page.cards()] == ["Beta", "Alfa"]
    assert not page.empty.isVisible()


def test_continue_page_empty_state(w):
    seed(w)
    w.show_page("continue")
    assert w.pages["continue"].empty.isVisible() and "Nada em andamento" in w.pages["continue"].empty.heading.text()


def test_cards_show_progress_bar_and_watched_state(w):
    a, b, c, d = seed(w)
    play(w, a, 25)
    play(w, b, 0, watched=True)
    w.show_page("library")
    cards = {c.video.title: c for c in w.pages["library"].cards()}
    assert cards["Alfa"].progress_bar.isVisibleTo(cards["Alfa"]) and cards["Alfa"].progress_bar.value() == 250
    assert "25% assistido" in cards["Alfa"].accessibleName()
    assert cards["Beta"].progress_bar.value() == 1000 and cards["Beta"].progress_bar.property("watched") is True
    assert "Assistido" in cards["Beta"].accessibleName()
    assert not cards["Gama"].progress_bar.isVisibleTo(cards["Gama"])


def test_card_menu_actions_follow_watch_state(w):
    a, b, c, d = seed(w)
    play(w, a, 25)
    play(w, b, 0, watched=True)
    w.show_page("library")
    cards = {c.video.title: c for c in w.pages["library"].cards()}
    assert {"Marcar como assistido", "Recomeçar do início"} <= set(cards["Alfa"].action_keys())
    assert {"Marcar como não assistido", "Recomeçar do início"} <= set(cards["Beta"].action_keys())
    keys = cards["Gama"].action_keys()
    assert "Marcar como assistido" in keys and "Recomeçar do início" not in keys
    assert "Remover do histórico" not in keys  # só nas páginas de histórico


def test_mark_watched_unwatched_restart_and_forget_through_menu(w):
    a, *_ = seed(w)
    play(w, a, 40)
    w.show_page("continue")
    card = w.pages["continue"].cards()[0]
    assert "Remover do histórico" in card.action_keys()
    action(card, "Marcar como assistido").trigger()
    assert w.progress.get(a.id).watched is True and w.pages["continue"].cards() == []  # saiu de "em andamento"
    w.show_page("library")
    action(next(c for c in w.pages["library"].cards() if c.video.id == a.id), "Marcar como não assistido").trigger()
    assert w.progress.get(a.id).watched is False
    play(w, a, 40)
    w.show_page("continue")
    action(w.pages["continue"].cards()[0], "Recomeçar do início").trigger()
    assert w.progress.get(a.id).position == 0.0 and w.pages["continue"].cards() == []
    play(w, a, 40)
    w.show_page("continue")
    action(w.pages["continue"].cards()[0], "Remover do histórico").trigger()
    assert w.progress.get(a.id) is None and w.library.get(a.id) is not None  # só o histórico foi esquecido


# ======================= histórico =======================
def test_history_groups_by_day_and_lists_rows(w):
    a, b, c, d = seed(w)
    play(w, a, 10)
    play(w, b, 20, when="2020-01-02T10:00:00+00:00")
    w.show_page("history")
    page = w.pages["history"]
    assert [h.text() for h in page.headings][0] == "Hoje" and len(page.rows) == 2
    assert page.headings[-1].text() != "Hoje"  # a data antiga ganha o próprio grupo
    assert [r.video.title for r in page.rows][0] == "Alfa"  # o mais recente primeiro
    assert not page.empty.isVisible() and page.clear_button.isVisible()
    assert "Remover do histórico" in page.rows[0].action_keys()


def test_history_empty_state_hides_clear_button(w):
    seed(w)
    w.show_page("history")
    page = w.pages["history"]
    assert page.empty.isVisible() and not page.clear_button.isVisible()


def test_clear_history_asks_and_keeps_everything_else(w, monkeypatch):
    a, b, *_ = seed(w)
    cat = w.org.create_category("Estudos")
    w.org.assign_categories([a.id], add=[cat.id])
    play(w, a, 10)
    play(w, b, 20)
    w.show_page("history")
    page = w.pages["history"]
    monkeypatch.setattr(type(page), "_confirm", lambda self: False)
    page.clear_button.click()
    assert len(page.rows) == 2
    monkeypatch.setattr(type(page), "_confirm", lambda self: True)
    page.clear_button.click()
    assert page.rows == [] and page.empty.isVisible()
    assert len(w.library.list_videos()) == 4 and w.org.video_category_ids(a.id) == [cat.id]
    assert w.top_bar.feedback.text() == "Histórico limpo."


def test_history_row_opens_video_and_menu_actions_work(w, qtbot):
    a, *_ = seed(w)
    play(w, a, 10)
    w.show_page("history")
    row = w.pages["history"].rows[0]
    next(x for x in row.menu_button.menu().actions() if x.text() == "Remover do histórico").trigger()
    assert w.progress.get(a.id) is None and w.pages["history"].rows == []


def test_playing_in_the_watch_page_creates_history_and_continue_entries(w):
    a, *_ = seed(w)
    w.open_saved_video(a.id)
    stub = w.watch_page.player._backend
    stub.position_changed.emit(30.0, 100.0)
    stub.state_changed.emit(True)
    stub.state_changed.emit(False)  # pausou: grava
    w.show_page("history")
    assert [r.video.title for r in w.pages["history"].rows] == ["Alfa"]
    w.show_page("continue")
    assert [c.video.title for c in w.pages["continue"].cards()] == ["Alfa"] and w.pages["continue"].cards()[0].progress_bar.value() == 300


def test_finishing_a_video_moves_it_from_continue_to_watched(w):
    a, *_ = seed(w)
    w.open_saved_video(a.id)
    stub = w.watch_page.player._backend
    stub.position_changed.emit(40.0, 100.0)
    stub.state_changed.emit(False)
    w.show_page("continue")
    assert len(w.pages["continue"].cards()) == 1
    w.open_saved_video(a.id)
    stub = w.watch_page.player._backend
    stub.position_changed.emit(99.0, 100.0)
    stub.ended.emit()
    w.show_page("continue")
    assert w.pages["continue"].cards() == [] and w.progress.get(a.id).watched is True


# ======================= playlists inteligentes =======================
def smart_cards(w):
    return {c.smart_key: c for c in w.pages["playlists"].smart_cards}


def test_smart_playlists_have_live_counts(w):
    a, b, c, d = seed(w)
    w.show_page("playlists")
    cards = smart_cards(w)
    assert list(cards) == ["continue", "unwatched", "downloaded", "recent"]
    assert cards["continue"].count_label.text() == "0 vídeos" and cards["unwatched"].count_label.text() == "4 vídeos"
    assert cards["recent"].count_label.text() == "4 vídeos" and cards["continue"].play_button is None
    play(w, a, 40)
    play(w, b, 0, watched=True)
    cards = smart_cards(w)
    assert cards["continue"].count_label.text() == "1 vídeo" and cards["unwatched"].count_label.text() == "2 vídeos"  # começado e assistido saem de "não assistidos"
    assert not cards["continue"].menu_button.isVisibleTo(cards["continue"])  # não são editáveis


def test_downloaded_smart_playlist_follows_files(w):
    a, *_ = seed(w)
    f = w.library.layout.videos / "a.mp4"
    f.write_bytes(b"0" * 50)
    w.library.attach_local_file(a.id, f, "720p")
    w.show_page("playlists")
    assert smart_cards(w)["downloaded"].count_label.text() == "1 vídeo"


def test_opening_a_smart_playlist_shows_library_with_that_query(w):
    a, b, c, d = seed(w)
    play(w, a, 40)
    w.show_page("playlists")
    smart_cards(w)["unwatched"].opened.emit(0)
    assert w.current_page == "library"
    assert {c.video.title for c in w.pages["library"].cards()} == {"Beta", "Gama", "Delta"}
    assert w.query_state.query.watch == q.WATCH_UNWATCHED and w.query_state.query.text == ""
    w.show_page("playlists")
    smart_cards(w)["continue"].opened.emit(0)
    assert [c.video.title for c in w.pages["library"].cards()] == ["Alfa"] and w.query_state.query.sort == q.SORT_LAST_PLAYED


def test_play_smart_playlist_opens_first_video_without_playlist_mode(w):
    a, b, *_ = seed(w)
    play(w, b, 40, when="2026-10-16T10:00:00+00:00")
    play(w, a, 50, when="2026-10-17T10:00:00+00:00")
    w.show_page("playlists")
    smart_cards(w)["continue"].play_requested.emit(0)
    assert w.current_page == "watch" and w.watch_page.player.video.title == "Alfa"
    assert w._playlist_id is None and not w.watch_page.playlist_label.isVisible()


def test_manual_playlists_still_work_below_the_smart_section(w, monkeypatch):
    from app.ui.dialogs.name_dialog import NameDialog

    seed(w)

    def fake(self):
        self.name_input.setText("Minha")
        self._save()
        return self.result()

    monkeypatch.setattr(NameDialog, "exec", fake)
    w.show_page("playlists")
    page = w.pages["playlists"]
    page.new_button.click()
    assert [c.name_label.text() for c in page.cards] == ["Minha"] and len(page.smart_cards) == 4
    assert page.smart_title.text() == "Playlists inteligentes" and page.mine_title.text() == "Minhas playlists"


def test_history_and_smart_texts_follow_language(w):
    a, *_ = seed(w)
    play(w, a, 40)
    combo = w.settings_page.language_combo
    combo.setCurrentIndex(combo.findData("en"))
    w.show_page("history")
    assert w.pages["history"].headings[0].text() == "Today" and w.pages["history"].clear_button.text() == "Clear history"
    w.show_page("playlists")
    assert smart_cards(w)["unwatched"].name_label.text() == "Unwatched" and w.pages["playlists"].smart_title.text() == "Smart playlists"
    w.show_page("library")
    assert "Mark as watched" in w.pages["library"].cards()[0].action_keys() or "Mark as unwatched" in w.pages["library"].cards()[0].action_keys()
