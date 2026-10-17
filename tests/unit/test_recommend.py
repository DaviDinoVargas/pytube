from app.domain import recommend
from app.domain.models import LOCAL_OK, Progress, Video
from app.domain.query import LibraryData


def video(i, channel="c", added="2026-01-01T00:00:00+00:00", status="none", title=None):
    return Video(source_id=f"s{i}", url=f"u{i}", id=i, channel=channel, added_at=added, local_status=status, title=title or f"V{i}", duration=600)


def data(videos, links=(), playlists=(), progress=()):
    return LibraryData(videos=list(videos), category_links=list(links), playlist_links=list(playlists), progress={p.video_id: p for p in progress})


def test_related_prefers_shared_categories_then_playlist_then_channel():
    base = video(1, channel="a")
    v = [base, video(2, channel="b"), video(3, channel="b"), video(4, channel="a"), video(5, channel="z")]
    d = data(v, links=[(1, 10), (2, 10), (3, 11)], playlists=[(7, 1, 0), (7, 3, 1)])
    ids = [x.id for x in recommend.related(base, d)]
    assert ids == [2, 3, 4]  # categoria (3) > playlist (2) = canal (2) com bônus de empate por data; 5 não tem nada em comum
    assert 5 not in ids and 1 not in ids


def test_related_pushes_watched_down_and_downloaded_up():
    base = video(1)
    v = [base, video(2), video(3), video(4, status=LOCAL_OK)]
    d = data(v, links=[(1, 1), (2, 1), (3, 1), (4, 1)], progress=[Progress(video_id=2, watched=True)])
    ids = [x.id for x in recommend.related(base, d)]
    assert ids[0] == 4 and ids[-1] == 2


def test_related_respects_limit_and_empty_library():
    base = video(1)
    d = data([base] + [video(i) for i in range(2, 20)], links=[(i, 1) for i in range(1, 20)])
    assert len(recommend.related(base, d, limit=5)) == 5
    assert recommend.related(base, data([base])) == []


def test_featured_order_in_progress_then_unwatched_then_newest():
    old, new = video(1, added="2026-01-01T00:00:00+00:00"), video(2, added="2026-02-01T00:00:00+00:00")
    assert recommend.featured(data([])) is None
    assert recommend.featured(data([old, new])).id == 2
    started = Progress(video_id=1, position=120, duration=600, last_played_at="2026-03-01T00:00:00+00:00")
    assert recommend.featured(data([old, new], progress=[started])).id == 1
    done = [Progress(video_id=1, watched=True), Progress(video_id=2, watched=True)]
    assert recommend.featured(data([old, new], progress=done)).id == 2  # tudo visto: o mais novo


def test_because_you_watched_skips_watched_and_needs_a_reference():
    a, b, c = video(1), video(2), video(3)
    assert recommend.because_you_watched(data([a, b, c])) == (None, [])
    d = data([a, b, c], links=[(1, 1), (2, 1), (3, 1)],
             progress=[Progress(video_id=1, position=60, last_played_at="2026-03-02T00:00:00+00:00"), Progress(video_id=3, watched=True, last_played_at="2026-03-01T00:00:00+00:00")])
    base, items = recommend.because_you_watched(d)
    assert base.id == 1 and [v.id for v in items] == [2]
    alone = data([a], progress=[Progress(video_id=1, position=60)])
    assert recommend.because_you_watched(alone) == (None, [])


def test_resume_label_position_only_for_videos_in_progress():
    a = video(1)
    d = data([a], progress=[Progress(video_id=1, position=90, duration=600)])
    assert recommend.resume_label_position(a, d) == 90
    assert recommend.resume_label_position(video(2), d) == 0.0
