from datetime import date, datetime, timedelta, timezone

import pytest

from app.domain import history as h
from app.domain import query as q
from app.domain.models import Progress, Video
from app.domain.query import LibraryData


def video(i, duration=100):
    return Video(source_id=f"v{i:010d}", url="u", title=f"V{i}", duration=duration, id=i)


def prog(i, pos=0, dur=100, watched=False, when="2026-10-17T12:00:00+00:00"):
    return Progress(i, position=pos, duration=dur, watched=watched, last_played_at=when)


@pytest.mark.parametrize("progress,expected", [
    (None, "none"), (prog(1, pos=3), "none"), (prog(1, pos=5), "in_progress"), (prog(1, pos=50), "in_progress"),
    (prog(1, pos=0, watched=True), "watched"), (prog(1, pos=50, watched=True), "watched"),
])
def test_watch_status(progress, expected):
    assert h.watch_status(progress) == expected


@pytest.mark.parametrize("progress,expected", [
    (None, 0.0), (prog(1, pos=25), 0.25), (prog(1, pos=250), 1.0), (prog(1, pos=0, watched=True), 1.0), (prog(1, pos=10, dur=0), 0.1),
])
def test_progress_fraction_uses_progress_or_video_duration(progress, expected):
    assert h.progress_fraction(video(1, 100), progress) == pytest.approx(expected)


def test_fraction_without_any_duration_is_zero():
    assert h.progress_fraction(video(1, None), prog(1, pos=10, dur=None)) == 0.0


def test_history_entries_most_recent_first_and_only_played():
    data = LibraryData(
        videos=[video(1), video(2), video(3)],
        progress={1: prog(1, when="2026-10-10T10:00:00+00:00"), 3: prog(3, when="2026-10-16T10:00:00+00:00")},
    )
    assert [e.video.id for e in h.history_entries(data)] == [3, 1]


def test_group_by_day_today_yesterday_older_and_unknown():
    today = date(2026, 10, 17)
    local = datetime(2026, 10, 17, 12, 0).astimezone()

    def at(days):
        return (local - timedelta(days=days)).isoformat()

    entries = [h.HistoryEntry(video(1), prog(1, when=at(0))), h.HistoryEntry(video(2), prog(2, when=at(1))),
               h.HistoryEntry(video(3), prog(3, when="lixo")), h.HistoryEntry(video(4), prog(4, when=at(5))),
               h.HistoryEntry(video(5), prog(5, when=at(0)))]
    groups = h.group_by_day(entries, today=today)
    keys = [k for k, _ in groups]
    assert keys[:2] == ["today", "yesterday"] and keys[-1] == "unknown" and keys[2] == date(2026, 10, 12)
    assert [e.video.id for e in dict(groups)["today"]] == [1, 5]


def test_smart_playlists_are_queries_not_stored_lists():
    assert set(h.SMART_PLAYLISTS) == set(h.SMART_ORDER)
    assert h.SMART_PLAYLISTS["continue"].watch == q.WATCH_IN_PROGRESS and h.SMART_PLAYLISTS["continue"].sort == q.SORT_LAST_PLAYED
    assert h.SMART_PLAYLISTS["downloaded"].state == q.STATE_DOWNLOADED
    assert h.SMART_PLAYLISTS["recent"].period == q.PERIOD_7


def test_smart_playlists_stay_current_as_data_changes():
    now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
    v1, v2 = video(1), video(2)
    v1.added_at = now.isoformat()
    v2.added_at = (now - timedelta(days=30)).isoformat()
    data = LibraryData(videos=[v1, v2], progress={})
    assert [v.id for v in q.apply_query(h.SMART_PLAYLISTS["unwatched"], data, now)] == [1, 2]
    assert [v.id for v in q.apply_query(h.SMART_PLAYLISTS["recent"], data, now)] == [1]
    data.progress[1] = prog(1, pos=40)
    assert [v.id for v in q.apply_query(h.SMART_PLAYLISTS["unwatched"], data, now)] == [2]
    assert [v.id for v in q.apply_query(h.SMART_PLAYLISTS["continue"], data, now)] == [1]
    data.progress[1] = prog(1, pos=0, watched=True)
    assert q.apply_query(h.SMART_PLAYLISTS["continue"], data, now) == []
