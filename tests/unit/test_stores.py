import json
import sqlite3

import pytest

from app.domain.errors import DuplicateError, NotFoundError, StorageError
from app.domain.models import LOCAL_OK, Category, Playlist, Progress, Video
from app.repositories.json_store import JsonStore
from app.repositories.sqlite_store import MIGRATIONS, SqliteStore


@pytest.fixture(params=["json", "sqlite"])
def store(request, tmp_path):
    if request.param == "json":
        s = JsonStore(tmp_path / "library.json")
    else:
        s = SqliteStore(tmp_path / "library.db")
    yield s
    s.close()


def video(n=1, **kw):
    kw.setdefault("title", f"Vídeo {n}")
    return Video(source_id=f"id{n:09d}"[:11], url=f"https://youtu.be/id{n}", **kw)


def test_add_get_find_and_list(store):
    v = store.add_video(video(1, channel="Canal"))
    assert v.id == 1
    assert store.get_video(1).title == "Vídeo 1"
    assert store.find_video("youtube", v.source_id).id == 1
    assert store.find_video("youtube", "naoexiste") is None
    store.add_video(video(2))
    assert [x.id for x in store.list_videos()] == [1, 2]


def test_duplicate_source_is_rejected(store):
    store.add_video(video(1))
    with pytest.raises(DuplicateError):
        store.add_video(video(1))


def test_update_video_keeps_local_state_separate(store):
    v = store.add_video(video(1))
    assert v.local_path is None and v.local_status == "none"
    v.local_path, v.local_status, v.local_size, v.local_quality = "videos/a.mp4", LOCAL_OK, 123, "720p"
    store.update_video(v)
    got = store.get_video(v.id)
    assert (got.local_path, got.local_status, got.local_size, got.local_quality) == ("videos/a.mp4", "ok", 123, "720p")


def test_update_missing_video_raises(store):
    ghost = video(9)
    ghost.id = 99
    with pytest.raises(NotFoundError):
        store.update_video(ghost)


def test_categories_are_unique_ignoring_case(store):
    store.add_category(Category(name="Estudos"))
    with pytest.raises(DuplicateError):
        store.add_category(Category(name="estudos"))


def test_rename_category_to_existing_name_fails(store):
    store.add_category(Category(name="Estudos"))
    music = store.add_category(Category(name="Música"))
    music.name = "ESTUDOS"
    with pytest.raises(DuplicateError):
        store.update_category(music)
    music.name = "Música ao vivo"
    store.update_category(music)
    assert [c.name for c in store.list_categories()] == ["Estudos", "Música ao vivo"]


def test_video_can_have_several_categories_and_deleting_one_keeps_video(store):
    v = store.add_video(video(1))
    a = store.add_category(Category(name="A"))
    b = store.add_category(Category(name="B"))
    store.set_video_categories(v.id, [a.id, b.id, a.id])
    assert store.get_video_category_ids(v.id) == [a.id, b.id]
    store.delete_category(a.id)
    assert store.get_video_category_ids(v.id) == [b.id]
    assert store.get_video(v.id) is not None


def test_set_categories_with_unknown_ids_raises_and_changes_nothing(store):
    v = store.add_video(video(1))
    a = store.add_category(Category(name="A"))
    store.set_video_categories(v.id, [a.id])
    with pytest.raises(NotFoundError):
        store.set_video_categories(v.id, [a.id, 999])
    assert store.get_video_category_ids(v.id) == [a.id]
    with pytest.raises(NotFoundError):
        store.set_video_categories(999, [a.id])


def test_playlist_order_is_persisted_and_reorderable(store):
    vids = [store.add_video(video(i)) for i in (1, 2, 3)]
    p = store.add_playlist(Playlist(name="Fila"))
    store.set_playlist_items(p.id, [vids[2].id, vids[0].id, vids[1].id])
    assert store.get_playlist_items(p.id) == [3, 1, 2]
    store.set_playlist_items(p.id, [2, 3])
    assert store.get_playlist_items(p.id) == [2, 3]


def test_removing_from_playlist_or_deleting_playlist_keeps_videos(store):
    v = store.add_video(video(1))
    p = store.add_playlist(Playlist(name="P"))
    store.set_playlist_items(p.id, [v.id])
    store.delete_playlist(p.id)
    assert store.list_playlists() == [] and store.get_video(v.id) is not None
    with pytest.raises(NotFoundError):
        store.set_playlist_items(p.id, [v.id])


def test_playlist_with_unknown_video_raises(store):
    p = store.add_playlist(Playlist(name="P"))
    with pytest.raises(NotFoundError):
        store.set_playlist_items(p.id, [42])


def test_deleting_video_cascades_links_but_not_other_videos(store):
    v1, v2 = store.add_video(video(1)), store.add_video(video(2))
    c = store.add_category(Category(name="C"))
    p = store.add_playlist(Playlist(name="P"))
    store.set_video_categories(v1.id, [c.id])
    store.set_playlist_items(p.id, [v1.id, v2.id])
    store.save_progress(Progress(video_id=v1.id, position=10))
    store.delete_video(v1.id)
    assert store.get_playlist_items(p.id) == [v2.id]
    assert store.get_video_category_ids(v1.id) == []
    assert store.get_progress(v1.id) is None
    assert store.list_categories()[0].id == c.id


def test_progress_roundtrip_and_overwrite(store):
    v = store.add_video(video(1))
    assert store.get_progress(v.id) is None
    store.save_progress(Progress(video_id=v.id, position=42.5, duration=300.0))
    store.save_progress(Progress(video_id=v.id, position=90.0, duration=300.0, watched=True))
    got = store.get_progress(v.id)
    assert (got.position, got.duration, got.watched) == (90.0, 300.0, True)
    with pytest.raises(NotFoundError):
        store.save_progress(Progress(video_id=999))
    store.clear_history()
    assert store.get_progress(v.id) is None and store.get_video(v.id) is not None


def test_unicode_and_quotes_are_stored_literally(store):
    nasty = "Robert'); DROP TABLE videos;-- ação \"aspas\" 日本語"
    v = store.add_video(video(1, title=nasty))
    assert store.get_video(v.id).title == nasty


def test_ids_are_not_reused_after_delete(store):
    a = store.add_video(video(1))
    b = store.add_video(video(2))
    store.delete_video(b.id)
    c = store.add_video(video(3))
    assert c.id > a.id


def _populate(s):
    v1, v2 = s.add_video(video(1, local_path="videos/a.mp4", local_status="ok")), s.add_video(video(2))
    c = s.add_category(Category(name="Estudos", color="#8B7CF6"))
    p = s.add_playlist(Playlist(name="Fila"))
    s.set_video_categories(v1.id, [c.id])
    s.set_playlist_items(p.id, [v2.id, v1.id])
    s.save_progress(Progress(video_id=v1.id, position=12.5, duration=100.0, watched=True, last_played_at="2025-01-01T00:00:00+00:00"))


@pytest.mark.parametrize("src_kind", ["json", "sqlite"])
@pytest.mark.parametrize("dst_kind", ["json", "sqlite"])
def test_migration_between_formats_preserves_everything(tmp_path, src_kind, dst_kind):
    def make(kind, name):
        return JsonStore(tmp_path / f"{name}.json") if kind == "json" else SqliteStore(tmp_path / f"{name}.db")

    src, dst = make(src_kind, "src"), make(dst_kind, "dst")
    _populate(src)
    dst.import_data(src.export_data())
    assert dst.export_data() == src.export_data()
    assert dst.get_playlist_items(1) == [2, 1]
    assert dst.get_progress(1).watched is True
    assert dst.add_video(video(3)).id == 3  # contador de ids continua depois do import
    src.close()
    dst.close()


def test_import_into_non_empty_store_is_refused(store):
    store.add_video(video(1))
    with pytest.raises(StorageError) as exc:
        store.import_data({"videos": []})
    assert exc.value.code == "target_not_empty"


def test_import_rejects_newer_schema(store):
    with pytest.raises(StorageError) as exc:
        store.import_data({"schema_version": 999})
    assert exc.value.code == "library_unsupported"


def test_json_data_survives_reopen_and_file_is_valid_json(tmp_path):
    path = tmp_path / "library.json"
    s = JsonStore(path)
    s.add_video(video(1))
    assert json.loads(path.read_text(encoding="utf-8"))["videos"][0]["title"] == "Vídeo 1"
    assert JsonStore(path).list_videos()[0].title == "Vídeo 1"
    assert not (tmp_path / "library.json.tmp").exists()


def test_json_corrupt_file_is_not_overwritten(tmp_path):
    path = tmp_path / "library.json"
    path.write_text("{ isto não é json", encoding="utf-8")
    with pytest.raises(StorageError) as exc:
        JsonStore(path)
    assert exc.value.code == "library_unreadable"
    assert path.read_text(encoding="utf-8") == "{ isto não é json"


def test_json_unknown_fields_from_future_versions_are_ignored(tmp_path):
    path = tmp_path / "library.json"
    s = JsonStore(path)
    s.add_video(video(1))
    data = json.loads(path.read_text(encoding="utf-8"))
    data["videos"][0]["campo_novo"] = "x"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert JsonStore(path).list_videos()[0].title == "Vídeo 1"


def test_sqlite_data_survives_reopen_and_sets_version(tmp_path):
    path = tmp_path / "library.db"
    SqliteStore(path).add_video(video(1))
    assert SqliteStore(path).list_videos()[0].title == "Vídeo 1"
    assert sqlite3.connect(path).execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)


def test_sqlite_garbage_file_raises_storage_error(tmp_path):
    path = tmp_path / "library.db"
    path.write_bytes(b"isto nao e um banco sqlite" * 50)
    with pytest.raises(StorageError):
        SqliteStore(path)


def test_sqlite_newer_version_is_refused(tmp_path):
    path = tmp_path / "library.db"
    SqliteStore(path).close()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA user_version = 99")
    conn.commit()
    conn.close()
    with pytest.raises(StorageError) as exc:
        SqliteStore(path)
    assert exc.value.code == "library_unsupported"


def test_delete_progress_is_scoped_to_one_video(store):
    v1, v2 = store.add_video(video(1)), store.add_video(video(2))
    store.save_progress(Progress(video_id=v1.id, position=10))
    store.save_progress(Progress(video_id=v2.id, position=20))
    store.delete_progress(v1.id)
    store.delete_progress(999)  # inexistente: sem erro
    assert store.get_progress(v1.id) is None and store.get_progress(v2.id).position == 20
    assert [p.video_id for p in store.list_progress()] == [v2.id]


def test_batch_listings_match_individual_queries(store):
    v1, v2 = store.add_video(video(1)), store.add_video(video(2))
    c = store.add_category(Category(name="A"))
    p = store.add_playlist(Playlist(name="P"))
    store.set_video_categories(v1.id, [c.id])
    store.set_playlist_items(p.id, [v2.id, v1.id])
    assert store.list_category_links() == [(v1.id, c.id)]
    assert store.list_playlist_links() == [(p.id, v2.id, 0), (p.id, v1.id, 1)]
