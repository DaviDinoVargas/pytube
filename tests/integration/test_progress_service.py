import pytest

from app.infrastructure.providers.chain import ProviderChain
from app.services.library_service import LibraryService
from app.services.progress_service import ProgressService
from app.services.storage_service import StorageManager
from app.services.thumbnail_service import ThumbnailService
from tests.fakes import VID, FakeProvider


@pytest.fixture(params=["sqlite", "json"])
def env(request, settings, tmp_path, qapp):
    storage = StorageManager(settings, tmp_path / "ad")
    storage.configure(tmp_path / "lib", "folder", request.param)
    provider = FakeProvider("f")
    library = LibraryService(storage, ProviderChain([provider]), ThumbnailService(lambda u: b""))
    video, _ = library.save_info(provider.fetch_info(VID))
    return ProgressService(library), library, video


def test_save_and_resume(env):
    service, library, video = env
    assert service.resume_position(video.id) == 0.0 and service.get(video.id) is None
    service.save(video.id, 42.5, 200)
    assert service.resume_position(video.id) == 42.5 and service.get(video.id).duration == 200


def test_watched_at_95_percent_resets_position_and_does_not_resume(env):
    service, library, video = env
    service.save(video.id, 195, 200)
    got = service.get(video.id)
    assert got.watched is True and got.position == 0.0
    assert service.resume_position(video.id) == 0.0


def test_watched_flag_survives_later_partial_viewing(env):
    service, library, video = env
    service.save(video.id, 195, 200)
    service.save(video.id, 30, 200)  # reassistiu um trecho
    assert service.get(video.id).watched is True and service.resume_position(video.id) == 0.0


def test_restart_clears_position_and_watched(env):
    service, library, video = env
    service.save(video.id, 195, 200)
    service.restart(video.id)
    got = service.get(video.id)
    assert got.watched is False and got.position == 0.0


def test_mark_watched_and_unwatched(env):
    service, library, video = env
    service.mark_watched(video.id)
    assert service.get(video.id).watched is True
    service.mark_watched(video.id, False)
    assert service.get(video.id).watched is False


def test_duration_is_kept_when_not_provided_later(env):
    service, library, video = env
    service.save(video.id, 10, 200)
    service.save(video.id, 20)
    assert service.get(video.id).duration == 200


def test_save_emits_library_changed(env, qtbot):
    service, library, video = env
    with qtbot.waitSignal(library.changed):
        service.save(video.id, 10, 200)


def test_inert_when_storage_not_ready(settings, tmp_path, qapp):
    library = LibraryService(StorageManager(settings, tmp_path / "ad"), ProviderChain([FakeProvider("f")]))
    service = ProgressService(library)
    assert service.get(1) is None and service.save(1, 10, 100) is None and service.resume_position(1) == 0.0
