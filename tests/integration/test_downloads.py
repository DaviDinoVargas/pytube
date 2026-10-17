import shutil
import threading
import time

import pytest

from app.domain.errors import DuplicateError, StorageError
from app.domain.filenames import safe_filename, unique_path
from app.domain.models import Video
from app.infrastructure.media.ffmpeg import FFmpegTools, MediaError
from app.infrastructure.providers.base import StreamOption
from app.infrastructure.providers.chain import ProviderChain
from app.services import download_service as ds
from app.services.download_service import DownloadManager
from app.services.library_service import LibraryService
from app.services.storage_service import StorageManager
from app.services.thumbnail_service import ThumbnailService
from tests.fakes import VID, MediaProvider
from tests.media import FFMPEG, FFPROBE, HAS_FFMPEG, make_media

pytestmark = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg não instalado")

DIRECT = StreamOption("progressive", "18", "mp4", 360, 30, 96, None, "avc1.42001E", "mp4a.40.2")
H264 = StreamOption("video", "137", "mp4", 1080, 30, 4000, None, "avc1.640028")
AAC = StreamOption("audio", "140", "m4a", None, None, 128, None, "", "mp4a.40.2")
VP9 = StreamOption("video", "248", "webm", 720, 30, 2000, None, "vp9")
OPUS = StreamOption("audio", "251", "webm", None, None, 160, None, "", "opus")
STREAMS = [DIRECT, H264, AAC, VP9, OPUS]


@pytest.fixture(scope="module")
def media(tmp_path_factory):
    return make_media(tmp_path_factory.mktemp("media"))


@pytest.fixture
def env(settings, tmp_path, qapp, media):
    storage = StorageManager(settings, tmp_path / "appdata")
    storage.configure(tmp_path / "lib", "folder", "sqlite")
    files = {"18": media["progressive_mp4"], "137": media["video_h264"], "140": media["audio_aac"],
             "248": media["video_vp9"], "251": media["audio_opus"]}
    provider = MediaProvider(files, STREAMS)
    chain = ProviderChain([provider])
    library = LibraryService(storage, chain, ThumbnailService(lambda u: b""))
    tools = FFmpegTools(FFMPEG, FFPROBE).check()
    manager = DownloadManager(library, chain, lambda: tools, max_concurrent=2)
    video, _ = library.save_info(provider.fetch_info(VID))
    yield manager, library, provider, video, tools
    manager.shutdown(3)


def wait_finished(qtbot, task, timeout=30000):
    qtbot.waitUntil(lambda: task.finished, timeout=timeout)
    return task


def tmp_is_empty(library):
    return not any(library.layout.tmp.iterdir())


def test_direct_download_completes_and_registers_verified_file(env, qtbot):
    manager, library, provider, video, tools = env
    changes = []
    library.changed.connect(lambda: changes.append(1))
    task = manager.enqueue(video.id, 360)
    wait_finished(qtbot, task)
    assert task.status == ds.COMPLETED and task.progress == 1.0 and task.label == "360p"
    got = library.get(video.id)
    assert got.local_status == "ok" and got.local_quality == "360p" and got.local_path == "Vídeo de teste [360p].mp4"
    assert (library.layout.videos / got.local_path).is_file() and got.local_size > 0
    assert tools.probe(library.layout.videos / got.local_path).has_audio
    assert tmp_is_empty(library) and changes


def test_merge_copy_for_h264_aac(env, qtbot):
    manager, library, provider, video, tools = env
    task = wait_finished(qtbot, manager.enqueue(video.id, 1080))
    assert task.status == ds.COMPLETED, task.error_detail
    info = tools.probe(library.local_path(library.get(video.id)))
    assert (info.vcodec, info.acodec) == ("h264", "aac")
    assert ("dQw4w9WgXcQ", "137") in provider.downloads and ("dQw4w9WgXcQ", "140") in provider.downloads


def test_vp9_is_recoded_into_playable_mp4(env, qtbot):
    manager, library, provider, video, tools = env
    task = wait_finished(qtbot, manager.enqueue(video.id, 720))
    assert task.status == ds.COMPLETED, task.error_detail
    info = tools.probe(library.local_path(library.get(video.id)))
    assert (info.vcodec, info.acodec) == ("h264", "aac")


def test_progress_is_monotonic_and_bounded(env, qtbot):
    manager, library, provider, video, tools = env
    provider.delay = 0.05
    seen = []
    manager.task_changed.connect(lambda tid: seen.append(manager.get(tid).progress))
    wait_finished(qtbot, manager.enqueue(video.id, 1080))
    assert seen == sorted(seen) and 0 <= min(seen) and max(seen) <= 1.0 and seen[-1] == 1.0
    assert any(0 < p < 1 for p in seen)


def test_garbage_file_is_rejected_and_not_registered(env, qtbot, media):
    manager, library, provider, video, tools = env
    provider.files["18"] = media["garbage"]
    task = wait_finished(qtbot, manager.enqueue(video.id, 360))
    assert task.status == ds.FAILED and task.error_code == "invalid_media"
    assert library.get(video.id).local_status == "none" and library.get(video.id).local_path is None
    assert list(library.layout.videos.iterdir()) == [] and tmp_is_empty(library)


def test_wrong_duration_is_rejected(env, qtbot):
    manager, library, provider, video, tools = env
    provider.duration = 600  # o provedor diz 10 min, o arquivo tem 2 s
    task = wait_finished(qtbot, manager.enqueue(video.id, 360))
    assert task.status == ds.FAILED and task.error_code == "invalid_media"
    assert library.get(video.id).local_status == "none"


def test_provider_failure_then_retry_succeeds(env, qtbot):
    manager, library, provider, video, tools = env
    provider.fail_times, provider.fail_code = 1, "network"
    task = wait_finished(qtbot, manager.enqueue(video.id, 360))
    assert task.status == ds.FAILED and task.error_code == "network"
    assert manager.status_for_video(video.id) == "failed" and tmp_is_empty(library)
    manager.retry(task.id)
    wait_finished(qtbot, task)
    assert task.status == ds.COMPLETED and task.attempt == 2 and task.error_code == ""
    assert manager.status_for_video(video.id) is None


def test_terminal_provider_error_is_reported_with_its_code(env, qtbot):
    manager, library, provider, video, tools = env
    provider.fail_times, provider.fail_code = 5, "drm"
    task = wait_finished(qtbot, manager.enqueue(video.id, 360))
    assert task.status == ds.FAILED and task.error_code == "drm"


def test_cancel_while_downloading_cleans_up(env, qtbot):
    manager, library, provider, video, tools = env
    provider.delay = 0.3
    task = manager.enqueue(video.id, 1080)
    qtbot.waitUntil(lambda: task.status == ds.DOWNLOADING and task.progress > 0, timeout=10000)
    manager.cancel(task.id)
    wait_finished(qtbot, task)
    assert task.status == ds.CANCELLED
    assert library.get(video.id).local_status == "none" and list(library.layout.videos.iterdir()) == []
    qtbot.waitUntil(lambda: tmp_is_empty(library), timeout=5000)
    manager.retry(task.id)
    provider.delay = 0
    wait_finished(qtbot, task)
    assert task.status == ds.COMPLETED


def test_cancel_queued_task_never_starts(env, qtbot):
    manager, library, provider, video, tools = env
    manager.set_max_concurrent(1)
    provider.delay = 0.2
    other, _ = library.save_info(provider.fetch_info("aaaaaaaaaaa"))
    first = manager.enqueue(video.id, 1080)
    second = manager.enqueue(other.id, 1080)
    assert second.status == ds.QUEUED
    manager.cancel(second.id)
    assert second.status == ds.CANCELLED
    manager.cancel(first.id)
    wait_finished(qtbot, first)
    assert ("aaaaaaaaaaa", "137") not in provider.downloads


def test_max_concurrent_is_respected(env, qtbot):
    manager, library, provider, video, tools = env
    provider.delay = 0.1
    manager.set_max_concurrent(1)
    others = [library.save_info(provider.fetch_info(f"vid{i:08d}"))[0] for i in range(2)]
    tasks = [manager.enqueue(v.id, 1080) for v in [video] + others]
    for t in tasks:
        wait_finished(qtbot, t)
    assert provider.max_running == 1 and all(t.status == ds.COMPLETED for t in tasks)
    assert manager.active_count() == 0


def test_two_run_in_parallel_when_allowed(env, qtbot):
    manager, library, provider, video, tools = env
    provider.delay = 0.15
    other, _ = library.save_info(provider.fetch_info("aaaaaaaaaaa"))
    a, b = manager.enqueue(video.id, 1080), manager.enqueue(other.id, 1080)
    wait_finished(qtbot, a)
    wait_finished(qtbot, b)
    assert provider.max_running >= 2


def test_duplicates_are_detected(env, qtbot):
    manager, library, provider, video, tools = env
    provider.delay = 0.1
    task = manager.enqueue(video.id, 360)
    with pytest.raises(DuplicateError) as exc:
        manager.enqueue(video.id, 360)
    assert "already_queued" in exc.value.detail
    wait_finished(qtbot, task)
    with pytest.raises(DuplicateError) as exc:
        manager.enqueue(video.id, 360)
    assert "already_downloaded" in exc.value.detail


def test_replace_creates_new_file_then_removes_old_one(env, qtbot):
    manager, library, provider, video, tools = env
    wait_finished(qtbot, manager.enqueue(video.id, 360))
    old = library.local_path(library.get(video.id))
    task = wait_finished(qtbot, manager.enqueue(video.id, 1080, replace=True))
    assert task.status == ds.COMPLETED
    new = library.local_path(library.get(video.id))
    assert new != old and new.is_file() and not old.exists()
    assert [p.name for p in library.layout.videos.iterdir()] == [new.name]


def test_never_overwrites_existing_file_with_same_name(env, qtbot):
    manager, library, provider, video, tools = env
    clash = library.layout.videos / "Vídeo de teste [360p].mp4"
    clash.write_bytes(b"arquivo do usuario")
    task = wait_finished(qtbot, manager.enqueue(video.id, 360))
    assert clash.read_bytes() == b"arquivo do usuario"
    assert library.get(video.id).local_path == "Vídeo de teste [360p] (2).mp4" and task.status == ds.COMPLETED


def test_unsafe_title_cannot_escape_library_folder(env, qtbot):
    manager, library, provider, video, tools = env
    provider.title = "../../etc/passwd:*?\"<>|"
    other, _ = library.save_info(provider.fetch_info("zzzzzzzzzzz"))
    task = wait_finished(qtbot, manager.enqueue(other.id, 360))
    path = library.local_path(library.get(other.id))
    assert task.status == ds.COMPLETED and path.parent == library.layout.videos.resolve()
    assert "/" not in path.name and "\\" not in path.name and path.is_relative_to(library.layout.videos.resolve())


def test_not_enough_disk_space_fails_before_downloading(settings, tmp_path, qapp, media):
    storage = StorageManager(settings, tmp_path / "appdata")
    storage.configure(tmp_path / "lib", "folder", "sqlite")
    sized = [StreamOption("video", "137", "mp4", 1080, 30, 4000, 500_000_000, "avc1.640028"),
             StreamOption("audio", "140", "m4a", None, None, 128, 5_000_000, "", "mp4a.40.2")]
    provider = MediaProvider({"137": media["video_h264"], "140": media["audio_aac"]}, sized)
    chain = ProviderChain([provider])
    library = LibraryService(storage, chain, ThumbnailService(lambda u: b""))
    manager = DownloadManager(library, chain, lambda: FFmpegTools(FFMPEG, FFPROBE).check(), free_space=lambda p: 100_000_000)
    video, _ = library.save_info(provider.fetch_info(VID))
    task = manager.enqueue(video.id, 1080)
    qtbot_wait(task)
    assert task.status == ds.FAILED and task.error_code == "no_space" and provider.downloads == []


def qtbot_wait(task, timeout=15):
    end = time.time() + timeout
    while not task.finished and time.time() < end:
        time.sleep(0.02)


def test_missing_ffmpeg_fails_with_clear_code(settings, tmp_path, qapp, media):
    storage = StorageManager(settings, tmp_path / "appdata")
    storage.configure(tmp_path / "lib", "folder", "sqlite")
    provider = MediaProvider({}, STREAMS)
    chain = ProviderChain([provider])
    library = LibraryService(storage, chain, ThumbnailService(lambda u: b""))

    def no_tools():
        raise MediaError("ffmpeg_missing", "não encontrado")

    manager = DownloadManager(library, chain, no_tools)
    video, _ = library.save_info(provider.fetch_info(VID))
    task = manager.enqueue(video.id, 360)
    qtbot_wait(task)
    assert task.status == ds.FAILED and task.error_code == "ffmpeg_missing" and provider.downloads == []


def test_unsupported_quality_fails_cleanly(env, qtbot):
    manager, library, provider, video, tools = env
    task = wait_finished(qtbot, manager.enqueue(video.id, 480))
    assert task.status == ds.FAILED and task.error_code == "unsupported"


def test_default_quality_is_the_best_available(env, qtbot):
    manager, library, provider, video, tools = env
    task = wait_finished(qtbot, manager.enqueue(video.id))
    assert task.height == 1080 and task.status == ds.COMPLETED


def test_remove_and_clear_only_finished_tasks(env, qtbot):
    manager, library, provider, video, tools = env
    provider.delay = 0.2
    running = manager.enqueue(video.id, 1080)
    manager.remove(running.id)  # ativa: ignorado
    assert manager.get(running.id) is not None
    manager.cancel(running.id)
    wait_finished(qtbot, running)
    manager.remove(running.id)
    assert manager.tasks() == []
    other = manager.enqueue(video.id, 360)
    provider.delay = 0
    wait_finished(qtbot, other)
    manager.clear_finished()
    assert manager.tasks() == []


def test_cleanup_orphans_removes_leftovers(env):
    manager, library, provider, video, tools = env
    leftover = library.layout.tmp / "99-abcdefghijk"
    leftover.mkdir()
    (leftover / "video.mp4").write_bytes(b"x")
    (library.layout.tmp / "solto.part").write_bytes(b"x")
    manager.cleanup_orphans()
    assert list(library.layout.tmp.iterdir()) == []


def test_shutdown_cancels_running_downloads(env, qtbot):
    manager, library, provider, video, tools = env
    provider.delay = 0.3
    task = manager.enqueue(video.id, 1080)
    qtbot.waitUntil(lambda: task.status == ds.DOWNLOADING, timeout=10000)
    manager.shutdown(10)
    assert task.status == ds.CANCELLED and tmp_is_empty(library)


def test_signals_fire_on_transitions(env, qtbot):
    manager, library, provider, video, tools = env
    transitions = []
    manager.queue_changed.connect(lambda: transitions.append(1))
    wait_finished(qtbot, manager.enqueue(video.id, 1080))
    assert len(transitions) >= 4  # entrou, resolvendo, baixando, juntando, finalizando, concluído


# ---------- nomes de arquivo ----------
@pytest.mark.parametrize("raw,expected", [
    ("Título normal", "Título normal"),
    ('a/b\\c:d*e?f"g<h>i|j', "a_b_c_d_e_f_g_h_i_j"),
    ("../../segredo", "_._segredo"),
    ("  espaços   demais  ", "espaços demais"),
    ("...", "video"),
    ("", "video"),
    ("CON", "video_CON"),
    ("nul.txt", "video_nul.txt"),
    (".oculto", "oculto"),
])
def test_safe_filename(raw, expected):
    assert safe_filename(raw) == expected


def test_safe_filename_limits_length_and_has_no_separators():
    out = safe_filename("x" * 500)
    assert len(out) == 120
    assert "/" not in safe_filename("../a") and "\\" not in safe_filename("..\\a")


def test_unique_path_never_collides(tmp_path):
    first = unique_path(tmp_path, "v", ".mp4")
    first.write_bytes(b"1")
    second = unique_path(tmp_path, "v", ".mp4")
    second.write_bytes(b"2")
    assert [first.name, second.name] == ["v.mp4", "v (2).mp4"] and unique_path(tmp_path, "v", ".mp4").name == "v (3).mp4"
