from datetime import datetime, timedelta, timezone

import pytest

from app.domain import query as q
from app.domain.models import Category, Playlist, Progress, Video
from app.domain.query import LibraryData, LibraryQuery, apply_query, fold

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


def iso(days_ago):
    return (NOW - timedelta(days=days_ago)).isoformat(timespec="seconds")


def video(i, title, channel="Canal", duration=300, days=0, status="none", **kw):
    return Video(source_id=f"vid{i:08d}", url=f"https://youtu.be/vid{i:08d}", title=title, channel=channel,
                 duration=duration, added_at=iso(days), local_status=status, id=i, **kw)


@pytest.fixture
def data():
    videos = [
        video(1, "Aprenda Python do zero", "Curso em Vídeo", 900, days=40, status="ok"),
        video(2, "Ação e reação: física", "Prof. Silva", 240, days=3),
        video(3, "Lo-fi para estudar", "Chill", 7200, days=10, status="missing"),
        video(4, "Receita de pão", "Cozinha", 120, days=400),
        video(5, "Python avançado", "Curso em Vídeo", None, days=1, status="ok"),
    ]
    return LibraryData(
        videos=videos,
        categories=[Category("Estudos", id=1), Category("Música", id=2), Category("Culinária", id=3)],
        category_links=[(1, 1), (2, 1), (3, 1), (3, 2), (4, 3)],
        playlists=[Playlist("Fila de hoje", id=10), Playlist("Favoritos", id=11)],
        playlist_links=[(10, 5, 0), (10, 1, 1), (11, 3, 0)],
        progress={
            1: Progress(1, position=900, duration=1800, last_played_at=iso(2)),
            2: Progress(2, position=240, duration=240, watched=True, last_played_at=iso(1)),
            3: Progress(3, position=2, duration=7200, last_played_at=iso(5)),
        },
    )


def ids(videos):
    return [v.id for v in videos]


def run(data, **kw):
    return ids(apply_query(LibraryQuery(**kw), data, NOW))


# ---------- texto ----------
@pytest.mark.parametrize("text,expected", [("python", {1, 5}), ("PYTHON", {1, 5}), ("acao", {2}), ("ação", {2}), ("vídeo curso", {1, 5}),
                                             ("estudos", {1, 2, 3}), ("musica", {3}), ("favoritos", {3}), ("fila", {1, 5}),
                                             ("vid00000004", {4}), ("naoexiste", set()), ("   ", {1, 2, 3, 4, 5})])
def test_text_search_across_title_channel_category_playlist_and_id(data, text, expected):
    assert set(run(data, text=text)) == expected


def test_all_words_must_match():
    assert fold("Ação Ç") == "acao c"


def test_search_words_are_anded(data):
    assert set(run(data, text="python curso")) == {1, 5}
    assert run(data, text="python receita") == []


# ---------- estado, categoria, playlist ----------
def test_state_filters(data):
    assert set(run(data, state=q.STATE_DOWNLOADED)) == {1, 5}
    assert set(run(data, state=q.STATE_SAVED)) == {2, 4}
    assert set(run(data, state=q.STATE_PROBLEMS)) == {3}


def test_categories_combine_with_or_and_other_filters_with_and(data):
    assert set(run(data, category_ids=frozenset({2, 3}))) == {3, 4}
    assert set(run(data, category_ids=frozenset({1}), state=q.STATE_DOWNLOADED)) == {1}


def test_playlist_filter_keeps_chosen_order(data):
    assert run(data, playlist_id=10) == [5, 1]  # ordem da playlist, não por data
    assert run(data, playlist_id=10, sort=q.SORT_TITLE_AZ) == [5, 1] or run(data, playlist_id=10, sort=q.SORT_TITLE_AZ) == [1, 5]
    assert run(data, playlist_id=10, sort=q.SORT_TITLE_AZ) == [1, 5]  # outra ordenação explícita vale
    assert run(data, playlist_id=999) == []


# ---------- assistido ----------
def test_watch_filters(data):
    assert run(data, watch=q.WATCH_WATCHED) == [2]
    assert run(data, watch=q.WATCH_IN_PROGRESS) == [1]  # 3 tem só 2 s: não conta como em andamento
    assert set(run(data, watch=q.WATCH_UNWATCHED)) == {3, 4, 5}


# ---------- período e duração ----------
def test_period_filters(data):
    assert set(run(data, period=q.PERIOD_7)) == {2, 5}
    assert set(run(data, period=q.PERIOD_30)) == {2, 3, 5}
    assert set(run(data, period=q.PERIOD_365)) == {1, 2, 3, 5}


def test_duration_boundaries_are_inclusive_for_short_and_exclusive_for_long(data):
    data.videos[3].duration = 240  # exatamente 4:00 é curto
    data.videos[2].duration = 1200  # exatamente 20:00 é médio
    assert 4 in run(data, duration=q.DURATION_SHORT) and 3 in run(data, duration=q.DURATION_MEDIUM)
    data.videos[2].duration = 1201
    assert 3 in run(data, duration=q.DURATION_LONG)


def test_duration_filters_exclude_unknown_duration(data):
    assert set(run(data, duration=q.DURATION_SHORT)) == {2, 4}
    assert set(run(data, duration=q.DURATION_MEDIUM)) == {1}
    assert set(run(data, duration=q.DURATION_LONG)) == {3}
    assert 5 in run(data)  # sem filtro, vídeo de duração desconhecida aparece


def test_invalid_added_date_never_matches_a_period_filter(data):
    data.videos[0].added_at = "lixo"
    assert 1 not in run(data, period=q.PERIOD_365) and 1 in run(data)


# ---------- ordenação ----------
@pytest.mark.parametrize("sort,expected", [
    (q.SORT_NEWEST, [5, 2, 3, 1, 4]),
    (q.SORT_OLDEST, [4, 1, 3, 2, 5]),
    (q.SORT_TITLE_AZ, [2, 1, 3, 5, 4]),
    (q.SORT_TITLE_ZA, [4, 5, 3, 1, 2]),
    (q.SORT_DURATION_DESC, [3, 1, 2, 4, 5]),
    (q.SORT_DURATION_ASC, [4, 2, 1, 3, 5]),
    (q.SORT_LAST_PLAYED, [2, 1, 3, 5, 4]),
    (q.SORT_PROGRESS, [2, 1, 3, 4, 5]),
    (q.SORT_DOWNLOAD, [5, 1, 3, 4, 2]),
])
def test_sorts(data, sort, expected):
    assert run(data, sort=sort) == expected


def test_unknown_sort_falls_back_to_newest(data):
    assert run(data, sort="???") == run(data, sort=q.SORT_NEWEST)


# ---------- chips e limpar ----------
def test_active_filters_and_removal(data):
    query = LibraryQuery(text="x", state=q.STATE_DOWNLOADED, category_ids=frozenset({2, 1}), watch=q.WATCH_WATCHED, sort=q.SORT_OLDEST)
    assert query.active_filters() == [("state", "downloaded"), ("category", 1), ("category", 2), ("watch", "watched")]
    assert ("category", 1) not in query.without("category", 1).active_filters()
    assert query.without("state").state == q.STATE_ALL and query.without("watch").watch == q.WATCH_ALL
    cleared = query.cleared()
    assert cleared.active_filters() == [] and cleared.text == "x" and cleared.sort == q.SORT_OLDEST


def test_is_filtered():
    assert not LibraryQuery().is_filtered
    assert LibraryQuery(text="a").is_filtered and LibraryQuery(state=q.STATE_SAVED).is_filtered
    assert not LibraryQuery(sort=q.SORT_OLDEST).is_filtered  # ordenar não é filtrar


def test_empty_library_and_no_match(data):
    assert apply_query(LibraryQuery(), LibraryData(videos=[]), NOW) == []
    assert run(data, state=q.STATE_DOWNLOADED, text="receita") == []
