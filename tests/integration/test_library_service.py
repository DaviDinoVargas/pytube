import pytest
from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QColor, QImage

from app.domain.states import DOWNLOADED, DOWNLOADING, FAILED, INVALID, MISSING, SAVED, format_duration, video_state
from app.infrastructure.providers.base import ProviderError
from app.infrastructure.providers.chain import ProviderChain
from app.services.library_service import LibraryService
from app.services.storage_service import StorageManager
from app.services.thumbnail_service import ThumbnailService, is_allowed_url, thumbnail_name
from tests.fakes import VID, FakeProvider


def jpeg_bytes(w=800, h=450):
    image = QImage(w, h, QImage.Format_RGB32)
    image.fill(QColor("#336699"))
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    image.save(buf, "JPG")
    return bytes(data)


@pytest.fixture
def env(settings, tmp_path, qapp):
    storage = StorageManager(settings, tmp_path / "appdata")
    storage.configure(tmp_path / "lib", "folder", "sqlite")
    provider = FakeProvider("fake")
    fetched = []

    def fetch(url):
        fetched.append(url)
        return jpeg_bytes()

    service = LibraryService(storage, ProviderChain([provider]), ThumbnailService(fetch))
    return service, storage, provider, fetched


def test_save_url_creates_video_with_thumbnail_and_no_local_file(env, qtbot):
    service, storage, provider, fetched = env
    with qtbot.waitSignal(service.changed):
        video, created = service.save_url(f"https://youtu.be/{VID}")
    assert created and video.id == 1 and video.title == "Vídeo de teste" and video.duration == 212
    assert video.local_path is None and video_state(video) == SAVED
    thumb = service.thumbnail_path(video)
    assert thumb is not None and thumb.parent == storage.layout.thumbnails
    assert QImage(str(thumb)).width() == 480  # reduzida
    assert fetched == ["https://i.ytimg.com/vi/x/hq.jpg"]


def test_saving_same_video_twice_does_not_duplicate_or_refetch(env):
    service, _, provider, _ = env
    service.save_url(VID and f"https://youtu.be/{VID}")
    video, created = service.save_url(f"https://www.youtube.com/watch?v={VID}")
    assert not created and len(service.list_videos()) == 1 and provider.fetch_calls == 1


def test_invalid_link_and_provider_failure_are_reported(env):
    service, _, provider, _ = env
    with pytest.raises(ProviderError) as exc:
        service.save_url("isso nao e link")
    assert exc.value.code == "unsupported"
    provider.error = "private"
    with pytest.raises(ProviderError) as exc:
        service.save_url(f"https://youtu.be/{VID}")
    assert exc.value.code == "private" and service.list_videos() == []


def test_failed_thumbnail_still_saves_video(env):
    service, storage, provider, _ = env
    service._thumbs = ThumbnailService(lambda url: (_ for _ in ()).throw(OSError("sem rede")))
    video, created = service.save_url(f"https://youtu.be/{VID}")
    assert created and video.thumbnail == "" and service.thumbnail_path(video) is None


def test_list_is_newest_first(env):
    service, _, provider, _ = env
    service.save_url("https://youtu.be/aaaaaaaaaaa")
    service.save_url("https://youtu.be/bbbbbbbbbbb")
    assert [v.source_id for v in service.list_videos()] == ["bbbbbbbbbbb", "aaaaaaaaaaa"]


def test_remove_keeps_local_file_by_default_and_deletes_only_when_asked(env, tmp_path):
    service, storage, *_ = env
    video, _ = service.save_url(f"https://youtu.be/{VID}")
    f = storage.layout.videos / "a.mp4"
    f.write_bytes(b"0" * 100)
    service.attach_local_file(video.id, f, "720p")
    service.remove(video.id)
    assert f.exists() and service.list_videos() == []
    video2, _ = service.save_url(f"https://youtu.be/{VID}")
    service.attach_local_file(video2.id, f, "720p")
    service.remove(video2.id, delete_file=True)
    assert not f.exists()


def test_remove_never_deletes_files_outside_library_folder(env, tmp_path):
    service, storage, *_ = env
    video, _ = service.save_url(f"https://youtu.be/{VID}")
    outside = tmp_path / "importante.txt"
    outside.write_text("não apague")
    video.local_path = "../../importante.txt"
    storage.store.update_video(video)
    service.remove(video.id, delete_file=True)
    assert outside.exists()


def test_attach_stores_relative_path_and_state_is_downloaded(env):
    service, storage, *_ = env
    video, _ = service.save_url(f"https://youtu.be/{VID}")
    f = storage.layout.videos / "sub" / "a.mp4"
    f.parent.mkdir()
    f.write_bytes(b"0" * 2048)
    got = service.attach_local_file(video.id, f, "1080p")
    assert got.local_path == "sub/a.mp4" and got.local_size == 2048 and got.local_quality == "1080p"
    assert video_state(got) == DOWNLOADED
    assert service.local_path(got) == f.resolve()


def test_validate_detects_missing_and_recovers_when_file_returns(env):
    service, storage, *_ = env
    video, _ = service.save_url(f"https://youtu.be/{VID}")
    f = storage.layout.videos / "a.mp4"
    f.write_bytes(b"0" * 100)
    video = service.attach_local_file(video.id, f)
    f.unlink()
    assert video_state(service.validate_local(video)) == MISSING
    assert service.get(video.id).local_status == "missing"  # persistido
    f.write_bytes(b"0" * 100)
    assert video_state(service.validate_local(service.get(video.id))) == DOWNLOADED


def test_empty_file_is_not_treated_as_downloaded(env):
    service, storage, *_ = env
    video, _ = service.save_url(f"https://youtu.be/{VID}")
    f = storage.layout.videos / "vazio.mp4"
    f.write_bytes(b"")
    video.local_path, video.local_status = "vazio.mp4", "ok"
    storage.store.update_video(video)
    assert video_state(service.validate_local(video)) == MISSING


def test_validate_all_reports_changes(env):
    service, storage, *_ = env
    video, _ = service.save_url(f"https://youtu.be/{VID}")
    f = storage.layout.videos / "a.mp4"
    f.write_bytes(b"0" * 10)
    service.attach_local_file(video.id, f)
    assert service.validate_all() is False
    f.unlink()
    assert service.validate_all() is True


def test_clear_local_file_returns_to_saved(env):
    service, storage, *_ = env
    video, _ = service.save_url(f"https://youtu.be/{VID}")
    f = storage.layout.videos / "a.mp4"
    f.write_bytes(b"0" * 10)
    service.attach_local_file(video.id, f)
    service.clear_local_file(video.id)
    assert video_state(service.get(video.id)) == SAVED


def test_service_is_inert_until_storage_is_configured(settings, tmp_path, qapp):
    service = LibraryService(StorageManager(settings, tmp_path / "ad"), ProviderChain([FakeProvider()]))
    assert not service.ready and service.list_videos() == [] and service.get(1) is None


def test_video_state_priority_and_duration_format():
    from app.domain.models import Video
    v = Video(source_id="a", url="u", local_status="ok")
    assert video_state(v) == DOWNLOADED and video_state(v, DOWNLOADING) == DOWNLOADING and video_state(v, FAILED) == FAILED
    assert video_state(Video(source_id="a", url="u", local_status="invalid")) == INVALID
    assert [format_duration(x) for x in (None, 0, 59, 61, 3600, 3725)] == ["", "", "0:59", "1:01", "1:00:00", "1:02:05"]


@pytest.mark.parametrize("url,ok", [
    ("https://i.ytimg.com/vi/x/hq.jpg", True),
    ("https://yt3.ggpht.com/a.jpg", True),
    ("http://i.ytimg.com/vi/x/hq.jpg", False),
    ("https://evil.com/i.ytimg.com.jpg", False),
    ("https://ytimg.com.evil.com/a.jpg", False),
    ("file:///etc/passwd", False),
    ("", False),
])
def test_thumbnail_url_allowlist(url, ok):
    assert is_allowed_url(url) is ok


def test_thumbnail_rejects_garbage_and_disallowed_hosts(env):
    service, storage, *_ = env
    thumbs = ThumbnailService(lambda url: b"nao sou imagem")
    assert thumbs.ensure(storage.layout, "youtube", "x", "https://i.ytimg.com/a.jpg") is None
    called = []
    thumbs = ThumbnailService(lambda url: called.append(url) or jpeg_bytes())
    assert thumbs.ensure(storage.layout, "youtube", "x", "https://evil.com/a.jpg") is None and called == []


def test_thumbnail_name_is_filesystem_safe():
    assert thumbnail_name("youtube", "../../x y") == "youtube_______x_y.jpg"
