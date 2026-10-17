import csv
import json
import time
from pathlib import Path

import pytest

from app.domain.errors import StorageError
from app.domain.models import Category, Playlist, Progress, Video
from app.infrastructure.providers.chain import ProviderChain
from app.repositories.base import SCHEMA_VERSION
from app.services import backup_service as bs
from app.services.backup_service import BackupService
from app.services.library_service import LibraryService
from app.services.storage_service import StorageManager
from app.services.thumbnail_service import ThumbnailService
from tests.fakes import FakeProvider


@pytest.fixture(params=["sqlite", "json"])
def env(request, settings, tmp_path, qapp):
    storage = StorageManager(settings, tmp_path / "ad")
    storage.configure(tmp_path / "lib", "folder", request.param)
    library = LibraryService(storage, ProviderChain([FakeProvider("f")]), ThumbnailService(lambda u: b""))
    return BackupService(library, storage), library, storage


def populate(library):
    store = library.store
    v1 = store.add_video(Video(source_id="aaaaaaaaaaa", url="u1", title="Alfa", channel="C", duration=100))
    v2 = store.add_video(Video(source_id="bbbbbbbbbbb", url="u2", title="=cmd|' /C calc'!A0", duration=50))
    c = store.add_category(Category("Estudos", "d", "#8B7CF6"))
    p = store.add_playlist(Playlist("Fila"))
    store.set_video_categories(v1.id, [c.id])
    store.set_playlist_items(p.id, [v2.id, v1.id])
    store.save_progress(Progress(v1.id, position=30, duration=100, watched=True, last_played_at="2026-01-01T00:00:00+00:00"))
    return v1, v2, c, p


# ---------- criar, listar, girar ----------
def test_create_writes_a_valid_backup_inside_backups_folder(env):
    backup, library, storage = env
    populate(library)
    path = backup.create()
    assert path.parent == storage.layout.backups and path.name.startswith("library-manual-")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["format"] == bs.FORMAT and payload["schema_version"] == SCHEMA_VERSION and payload["kind"] == "manual"
    assert len(payload["data"]["videos"]) == 2
    bs.validate_payload(payload)
    assert not list(storage.layout.backups.glob("*.tmp"))


def test_two_backups_in_the_same_second_do_not_overwrite(env):
    backup, library, _ = env
    populate(library)
    assert backup.create() != backup.create() and len(backup.list()) == 2


def test_list_ignores_foreign_files_and_orders_newest_first(env):
    backup, library, storage = env
    populate(library)
    (storage.layout.backups / "library-lixo.json").write_text("{ não é json")
    (storage.layout.backups / "library-outro.json").write_text(json.dumps({"format": "outra-coisa"}))
    (storage.layout.backups / "notas.txt").write_text("oi")
    first = backup.create("manual")
    time.sleep(1.1)
    second = backup.create("manual")
    assert [i.path for i in backup.list()] == [second, first] and backup.list()[0].videos == 2


def test_automatic_backups_rotate_but_manual_never_do(env):
    backup, library, _ = env
    populate(library)
    manual = [backup.create("manual") for _ in range(7)]
    for _ in range(bs.KEEP_AUTOMATIC + 3):
        backup.create("auto")
    kinds = [i.kind for i in backup.list()]
    assert kinds.count("auto") == bs.KEEP_AUTOMATIC and kinds.count("manual") == 7
    assert all(p.exists() for p in manual)


def test_auto_backup_only_when_due_and_not_for_empty_library(env):
    backup, library, _ = env
    assert backup.auto_backup_if_due() is None  # biblioteca vazia: nada a guardar
    populate(library)
    assert backup.auto_backup_if_due() is not None
    assert backup.auto_backup_if_due() is None  # acabou de fazer
    assert backup.auto_backup_if_due(hours=0) is not None


# ---------- restaurar ----------
def test_restore_brings_back_everything_exactly(env):
    backup, library, _ = env
    v1, v2, c, p = populate(library)
    snapshot = library.store.export_data()
    path = backup.create()
    library.store.delete_video(v1.id)
    library.store.delete_category(c.id)
    library.store.add_video(Video(source_id="cccccccccc1", url="x", title="Lixo"))
    result = backup.restore(path)
    assert library.store.export_data() == snapshot
    assert result["videos"] == 2 and result["safety_backup"] is not None and result["safety_backup"].exists()


def test_restore_makes_a_pre_restore_backup_of_the_current_state(env):
    backup, library, _ = env
    populate(library)
    path = backup.create()
    library.store.add_video(Video(source_id="cccccccccc1", url="x", title="Nova"))
    result = backup.restore(path)
    saved = json.loads(result["safety_backup"].read_text(encoding="utf-8"))
    assert saved["kind"] == "pre-restore" and len(saved["data"]["videos"]) == 3  # o estado de antes da restauração


def test_restore_into_empty_library_skips_safety_backup(env):
    backup, library, storage = env
    populate(library)
    path = backup.create()
    library.store.replace_data({"schema_version": SCHEMA_VERSION})
    assert library.store.is_empty()
    assert backup.restore(path)["safety_backup"] is None


def test_restore_revalidates_files_missing_on_this_computer(env):
    backup, library, storage = env
    v1, *_ = populate(library)
    f = storage.layout.videos / "a.mp4"
    f.write_bytes(b"0" * 20)
    library.attach_local_file(v1.id, f, "720p")
    path = backup.create()
    f.unlink()  # como num computador novo: o arquivo não veio junto
    backup.restore(path)
    assert library.get(v1.id).local_status == "missing"


@pytest.mark.parametrize("mutate,code", [
    (lambda p: p.update(format="outra"), "backup_invalid"),
    (lambda p: p.update(schema_version=SCHEMA_VERSION + 5), "library_unsupported"),
    (lambda p: p.update(schema_version="1"), "backup_invalid"),
    (lambda p: p.update(schema_version=True), "backup_invalid"),
    (lambda p: p.update(data=[]), "backup_invalid"),
    (lambda p: p["data"].update(videos="x"), "backup_invalid"),
    (lambda p: p["data"]["videos"].append({"id": 1, "source_id": "x", "url": "u"}), "backup_invalid"),  # id repetido
    (lambda p: p["data"]["videos"][0].pop("url"), "backup_invalid"),
    (lambda p: p["data"]["videos"][0].update(title=123), "backup_invalid"),
    (lambda p: p["data"]["categories"][0].update(name="  "), "backup_invalid"),
    (lambda p: p["data"]["video_categories"].append([999, 1]), "backup_invalid"),
    (lambda p: p["data"]["playlist_items"].append([1, 999, 0]), "backup_invalid"),
    (lambda p: p["data"]["progress"].append({"video_id": 999}), "backup_invalid"),
])
def test_invalid_backups_are_rejected_and_library_stays_intact(env, mutate, code):
    backup, library, storage = env
    populate(library)
    payload = json.loads(backup.create().read_text(encoding="utf-8"))
    mutate(payload)
    bad = storage.layout.backups / "ruim.json"
    bad.write_text(json.dumps(payload), encoding="utf-8")
    before = library.store.export_data()
    with pytest.raises(StorageError) as exc:
        backup.restore(bad)
    assert exc.value.code == code and library.store.export_data() == before


@pytest.mark.parametrize("content", ["", "{ isso não é json", "[]", "null", "123"])
def test_garbage_files_are_rejected(env, content):
    backup, library, storage = env
    populate(library)
    bad = storage.layout.backups / "lixo.json"
    bad.write_text(content, encoding="utf-8")
    before = library.store.export_data()
    with pytest.raises(StorageError) as exc:
        backup.restore(bad)
    assert exc.value.code == "backup_invalid" and library.store.export_data() == before


def test_missing_and_oversized_files(env, monkeypatch):
    backup, library, storage = env
    with pytest.raises(StorageError) as exc:
        backup.restore(storage.layout.backups / "nao_existe.json")
    assert exc.value.code == "backup_unreadable"
    big = storage.layout.backups / "grande.json"
    big.write_text("{}")
    monkeypatch.setattr(bs, "MAX_BYTES", 1)
    with pytest.raises(StorageError) as exc:
        backup.restore(big)
    assert exc.value.code == "backup_invalid"


def test_database_failure_during_restore_rolls_back(settings, tmp_path, qapp):
    storage = StorageManager(settings, tmp_path / "ad")
    storage.configure(tmp_path / "lib", "folder", "sqlite")
    library = LibraryService(storage, ProviderChain([FakeProvider("f")]), ThumbnailService(lambda u: b""))
    populate(library)
    before = library.store.export_data()
    broken = {"schema_version": 1, "videos": [{"id": 1, "source_id": "x", "url": "u", "added_at": "a"}],
              "video_categories": [[1, 77]]}  # referência inexistente: o banco recusa
    with pytest.raises(StorageError) as exc:
        library.store.replace_data(broken)
    assert exc.value.code == "library_import_invalid" and library.store.export_data() == before


def test_export_to_custom_path_and_import_back(env, tmp_path):
    backup, library, _ = env
    populate(library)
    target = tmp_path / "fora" / "minha-biblioteca.json"
    backup.export_to(target)
    assert json.loads(target.read_text(encoding="utf-8"))["kind"] == "export"
    snapshot = library.store.export_data()
    library.store.replace_data({"schema_version": SCHEMA_VERSION})
    backup.restore(target)
    assert library.store.export_data() == snapshot


# ---------- CSV ----------
def test_csv_export_is_readable_and_neutralizes_formulas(env, tmp_path):
    backup, library, _ = env
    populate(library)
    path = backup.export_csv(tmp_path / "lista.csv")
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # BOM para o Excel
    rows = list(csv.reader(path.read_text(encoding="utf-8-sig").splitlines()))
    assert rows[0][0] == "titulo" and len(rows) == 3
    by_title = {r[0]: r for r in rows[1:]}
    assert by_title["Alfa"][5] == "Estudos" and by_title["Alfa"][3] == "100"
    formula = next(r[0] for r in rows[1:] if "cmd" in r[0])
    assert formula.startswith("'=")  # não vira fórmula no Excel


# ---------- segurança: nunca apagar fora da biblioteca ----------
def test_delete_never_touches_files_outside_the_library_even_with_absolute_path(env, tmp_path):
    _, library, storage = env
    v1, *_ = populate(library)
    precious = tmp_path / "meus-documentos" / "importante.mp4"
    precious.parent.mkdir()
    precious.write_bytes(b"nao apague")
    video = library.get(v1.id)
    video.local_path, video.local_status = str(precious), "ok"  # ex.: veio de um backup adulterado
    library.store.update_video(video)
    assert library.delete_local_file(v1.id) == 0 and precious.exists()
    video = library.get(v1.id)
    video.local_path, video.local_status = str(precious), "ok"
    library.store.update_video(video)
    library.remove(v1.id, delete_file=True)
    assert precious.exists() and library.get(v1.id) is None


def test_delete_local_file_frees_bytes_and_returns_video_to_saved(env):
    _, library, storage = env
    v1, *_ = populate(library)
    f = storage.layout.videos / "a.mp4"
    f.write_bytes(b"0" * 1234)
    library.attach_local_file(v1.id, f, "720p")
    assert library.delete_local_file(v1.id) == 1234 and not f.exists()
    got = library.get(v1.id)
    assert got.local_status == "none" and got.local_path is None and got.title == "Alfa"  # o registro fica


def test_is_inside_library(env, tmp_path):
    _, library, storage = env
    assert library.is_inside_library(storage.layout.videos / "x.mp4")
    assert not library.is_inside_library(tmp_path / "outro.mp4")
    assert not library.is_inside_library(storage.layout.videos / ".." / "x.mp4")
