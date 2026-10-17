import sqlite3

import pytest

from app.domain.models import Video
from app.repositories.json_store import JsonStore
from app.repositories.sqlite_store import MIGRATIONS, SqliteStore


@pytest.fixture(params=["json", "sqlite"])
def store(request, tmp_path):
    s = JsonStore(tmp_path / "l.json") if request.param == "json" else SqliteStore(tmp_path / "l.db")
    yield s
    s.close()


def video(n=1, **kw):
    return Video(source_id=f"id{n:09d}"[:11], url=f"u{n}", title=f"V{n}", **kw)


def test_notes_default_to_empty_and_persist_on_update(store):
    v = store.add_video(video(1))
    assert v.notes == "" and store.get_video(v.id).notes == ""
    v.notes = "Rever aos 12:30 — ótimo trecho sobre índices"
    store.update_video(v)
    assert store.get_video(v.id).notes == "Rever aos 12:30 — ótimo trecho sobre índices"


def test_notes_travel_through_export_and_import(store, tmp_path):
    v = store.add_video(video(1, notes="nota"))
    data = store.export_data()
    assert data["videos"][0]["notes"] == "nota"
    other = SqliteStore(tmp_path / "other.db")
    other.import_data(data)
    assert other.get_video(1).notes == "nota"
    other.close()


def test_database_created_before_notes_is_migrated_and_keeps_its_data(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    for statement in MIGRATIONS[0].split(";"):
        if statement.strip():
            conn.execute(statement)
    conn.execute("PRAGMA user_version = 1")
    conn.execute(
        "INSERT INTO videos (source, source_id, url, title, added_at) VALUES ('youtube', 'aaaaaaaaaaa', 'u', 'Antigo', '2026-01-01T00:00:00+00:00')"
    )
    conn.commit()
    conn.close()
    store = SqliteStore(path)
    old = store.list_videos()[0]
    assert old.title == "Antigo" and old.notes == ""
    old.notes = "agora tem nota"
    store.update_video(old)
    assert store.get_video(old.id).notes == "agora tem nota"
    assert sqlite3.connect(path).execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS) == 2
    assert (tmp_path / "old.db.bak-v1").exists()  # cópia de segurança antes de migrar


def test_json_library_without_notes_still_loads(tmp_path):
    import json

    path = tmp_path / "l.json"
    path.write_text(json.dumps({"schema_version": 1, "videos": [{"id": 1, "source_id": "aaaaaaaaaaa", "url": "u", "title": "T"}]}), encoding="utf-8")
    store = JsonStore(path)
    assert store.list_videos()[0].notes == ""


def test_library_service_saves_trimmed_notes_without_notifying(settings, tmp_path, qapp):
    from app.infrastructure.providers.chain import ProviderChain
    from app.services.library_service import NOTES_LIMIT, LibraryService
    from app.services.storage_service import StorageManager
    from app.services.thumbnail_service import ThumbnailService
    from tests.fakes import FakeProvider

    storage = StorageManager(settings, tmp_path / "ad")
    storage.configure(tmp_path / "lib", "folder", "sqlite")
    library = LibraryService(storage, ProviderChain([FakeProvider("f")]), ThumbnailService(lambda u: b""))
    v, _ = library.save_info(FakeProvider("f").fetch_info("vid00000001"))
    changes = []
    library.changed.connect(lambda: changes.append(1))
    assert library.set_notes(v.id, "x" * (NOTES_LIMIT + 50)) == "x" * NOTES_LIMIT
    assert library.get(v.id).notes == "x" * NOTES_LIMIT and changes == []
    assert library.set_notes(v.id, None) == "" and library.set_notes(999, "a") is None
