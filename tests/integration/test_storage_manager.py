import os
import sys

import pytest

from app.domain.errors import StorageError
from app.domain.models import Category, Video
from app.services.storage_service import (
    FORMAT_JSON,
    FORMAT_SQLITE,
    MODE_DATABASE,
    MODE_FOLDER,
    STATUS_READY,
    STATUS_ROOT_MISSING,
    STATUS_UNCONFIGURED,
    SUBFOLDERS,
    StorageLayout,
    StorageManager,
    format_bytes,
    validate_root,
)


@pytest.fixture
def manager(settings, tmp_path):
    return StorageManager(settings, tmp_path / "appdata")


def vid(n):
    return Video(source_id=f"abcdefghi{n:02d}", url=f"https://youtu.be/abcdefghi{n:02d}", title=f"V{n}")


def test_unconfigured_by_default(manager):
    assert manager.status() == STATUS_UNCONFIGURED
    with pytest.raises(StorageError) as exc:
        manager.store
    assert exc.value.code == "storage_not_ready"


def test_configure_creates_all_subfolders_immediately(manager, tmp_path):
    root = tmp_path / "meus videos"
    manager.configure(root, MODE_FOLDER, FORMAT_SQLITE)
    for name in SUBFOLDERS:
        assert (root / name).is_dir(), name
    assert manager.status() == STATUS_READY


def test_folder_mode_keeps_library_inside_chosen_folder(manager, tmp_path):
    root = tmp_path / "lib"
    manager.configure(root, MODE_FOLDER, FORMAT_JSON)
    manager.store.add_video(vid(1))
    assert (root / "data" / "library.json").is_file()
    assert not (tmp_path / "appdata").exists()


def test_folder_mode_sqlite_is_portable_inside_folder(manager, tmp_path):
    root = tmp_path / "lib"
    manager.configure(root, MODE_FOLDER, FORMAT_SQLITE)
    manager.store.add_video(vid(1))
    assert (root / "data" / "library.db").is_file()


def test_database_mode_keeps_library_in_app_data_but_media_folders_in_root(manager, tmp_path):
    root = tmp_path / "lib"
    manager.configure(root, MODE_DATABASE, FORMAT_JSON)  # formato é ignorado: banco é sempre SQLite
    manager.store.add_video(vid(1))
    assert (tmp_path / "appdata" / "library.db").is_file()
    assert (root / "videos").is_dir()
    assert not (root / "data" / "library.json").exists()


def test_configuration_persists_across_restart(settings, tmp_path):
    first = StorageManager(settings, tmp_path / "appdata")
    first.configure(tmp_path / "lib", MODE_FOLDER, FORMAT_JSON)
    first.store.add_video(vid(1))
    first.close()
    second = StorageManager(settings, tmp_path / "appdata")
    assert second.status() == STATUS_READY
    assert (second.config.mode, second.config.format) == (MODE_FOLDER, FORMAT_JSON)
    assert second.store.list_videos()[0].title == "V1"


def test_missing_root_is_reported_not_silently_recreated(settings, tmp_path):
    first = StorageManager(settings, tmp_path / "appdata")
    first.configure(tmp_path / "lib", MODE_FOLDER, FORMAT_SQLITE)
    first.close()
    import shutil
    shutil.rmtree(tmp_path / "lib")
    second = StorageManager(settings, tmp_path / "appdata")
    assert second.status() == STATUS_ROOT_MISSING
    assert not (tmp_path / "lib").exists()


def test_migrate_json_to_sqlite_copies_records_and_keeps_original(manager, tmp_path):
    manager.configure(tmp_path / "a", MODE_FOLDER, FORMAT_JSON)
    v = manager.store.add_video(vid(1))
    manager.store.set_video_categories(v.id, [manager.store.add_category(Category(name="Estudos")).id])
    plan = manager.plan(tmp_path / "b", MODE_FOLDER, FORMAT_SQLITE)
    assert (plan.videos, plan.categories, plan.target_has_data, plan.same_location) == (1, 1, False, False)
    manager.configure(tmp_path / "b", MODE_FOLDER, FORMAT_SQLITE, migrate=True)
    assert manager.store.kind == "sqlite"
    assert manager.store.list_videos()[0].title == "V1"
    assert manager.store.get_video_category_ids(1) == [1]
    assert (tmp_path / "a" / "data" / "library.json").is_file()


def test_changing_folder_without_migrate_starts_empty_and_leaves_old_data(manager, tmp_path):
    manager.configure(tmp_path / "a", MODE_FOLDER, FORMAT_SQLITE)
    manager.store.add_video(vid(1))
    manager.configure(tmp_path / "b", MODE_FOLDER, FORMAT_SQLITE)
    assert manager.store.list_videos() == []
    manager.configure(tmp_path / "a", MODE_FOLDER, FORMAT_SQLITE)
    assert manager.store.list_videos()[0].title == "V1"


def test_migrate_refuses_to_overwrite_a_non_empty_target(manager, tmp_path):
    manager.configure(tmp_path / "b", MODE_FOLDER, FORMAT_SQLITE)
    manager.store.add_video(vid(2))
    manager.configure(tmp_path / "a", MODE_FOLDER, FORMAT_SQLITE)
    manager.store.add_video(vid(1))
    assert manager.plan(tmp_path / "b", MODE_FOLDER, FORMAT_SQLITE).target_has_data is True
    with pytest.raises(StorageError) as exc:
        manager.configure(tmp_path / "b", MODE_FOLDER, FORMAT_SQLITE, migrate=True)
    assert exc.value.code == "target_not_empty"
    # nada mudou: continua na pasta "a"
    assert manager.config.root == tmp_path / "a"
    assert manager.store.list_videos()[0].title == "V1"


def test_failed_configure_does_not_change_current_setup(manager, tmp_path):
    manager.configure(tmp_path / "a", MODE_FOLDER, FORMAT_SQLITE)
    blocker = tmp_path / "arquivo"
    blocker.write_text("x")
    with pytest.raises(StorageError) as exc:
        manager.configure(blocker, MODE_FOLDER, FORMAT_SQLITE)
    assert exc.value.code == "path_not_directory"
    assert manager.config.root == tmp_path / "a"


def test_changing_only_mode_in_same_root_migrates(manager, tmp_path):
    root = tmp_path / "a"
    manager.configure(root, MODE_FOLDER, FORMAT_SQLITE)
    manager.store.add_video(vid(1))
    manager.configure(root, MODE_DATABASE, FORMAT_SQLITE, migrate=True)
    assert manager.store.list_videos()[0].title == "V1"
    assert (tmp_path / "appdata" / "library.db").is_file()


def test_usage_counts_only_video_files(manager, tmp_path):
    manager.configure(tmp_path / "a", MODE_FOLDER, FORMAT_SQLITE)
    (tmp_path / "a" / "videos" / "x.mp4").write_bytes(b"0" * 2048)
    (tmp_path / "a" / "thumbnails" / "t.jpg").write_bytes(b"0" * 999)
    usage = manager.usage()
    assert (usage["videos_bytes"], usage["video_files"]) == (2048, 1)
    assert usage["free"] > 0


@pytest.mark.parametrize("bad,code", [("", "path_empty"), ("   ", "path_empty"), ("relativo/pasta", "path_not_absolute")])
def test_validate_root_rejects_bad_input(bad, code):
    with pytest.raises(StorageError) as exc:
        validate_root(bad)
    assert exc.value.code == code


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0, reason="permissões de pasta não valem para root")
def test_validate_root_rejects_unwritable_folder(tmp_path):
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o500)
    with pytest.raises(StorageError) as exc:
        validate_root(ro)
    assert exc.value.code == "path_not_writable"
    ro.chmod(0o700)


def test_validate_root_cleans_up_probe_file(tmp_path):
    validate_root(tmp_path / "novo")
    assert list((tmp_path / "novo").iterdir()) == []


def test_layout_stores_paths_relative_to_videos_and_blocks_escape(tmp_path):
    layout = StorageLayout(tmp_path / "lib")
    layout.create()
    inside = layout.videos / "canal" / "a.mp4"
    assert layout.to_stored(inside) == "canal/a.mp4"
    assert layout.resolve("canal/a.mp4") == inside.resolve()
    outside = tmp_path / "outra" / "b.mp4"
    assert layout.to_stored(outside) == str(outside)
    assert layout.resolve(str(outside)) == outside
    with pytest.raises(StorageError) as exc:
        layout.resolve("../../etc/passwd")
    assert exc.value.code == "path_escapes_root"


def test_moved_folder_still_resolves_stored_paths(tmp_path):
    old = StorageLayout(tmp_path / "old")
    old.create()
    stored = old.to_stored(old.videos / "a.mp4")
    new = StorageLayout(tmp_path / "new")
    assert new.resolve(stored) == (new.videos / "a.mp4").resolve()


def test_format_bytes():
    assert format_bytes(0) == "0 B"
    assert format_bytes(1536) == "1.5 KB"
    assert format_bytes(5 * 1024**3) == "5.0 GB"


def test_reconfiguring_same_location_before_store_is_opened(settings, tmp_path):
    first = StorageManager(settings, tmp_path / "appdata")
    first.configure(tmp_path / "a", MODE_FOLDER, FORMAT_SQLITE)
    first.close()
    second = StorageManager(settings, tmp_path / "appdata")
    second.configure(tmp_path / "a", MODE_FOLDER, FORMAT_SQLITE)
    assert second.store is not None and second.store.list_videos() == []
