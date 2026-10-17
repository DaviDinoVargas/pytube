import subprocess
import sys
from pathlib import Path

import pytest

from app.domain.errors import StorageError
from app.domain.models import Category
from app.infrastructure.media.ffmpeg import FFmpegTools, MediaError
from app.infrastructure.providers.chain import ProviderChain
from app.services import diagnostics_service as dg
from app.services import provider_service as ps
from app.services.library_service import LibraryService
from app.services.maintenance_service import MaintenanceService
from app.services.storage_service import StorageManager
from app.services.thumbnail_service import ThumbnailService
from tests.fakes import VID, FakeProvider
from tests.media import FFMPEG, FFPROBE, HAS_FFMPEG, make_media


@pytest.fixture
def env(settings, tmp_path, qapp):
    storage = StorageManager(settings, tmp_path / "ad")
    storage.configure(tmp_path / "lib", "folder", "sqlite")
    provider = FakeProvider("f")
    library = LibraryService(storage, ProviderChain([provider]), ThumbnailService(lambda u: b""))
    return MaintenanceService(library, storage, ThumbnailService(lambda u: b"")), library, storage, provider


def video(library, provider, i, title="V"):
    return library.save_info(FakeProvider("f", title=f"{title}{i}").fetch_info(f"vid{i:08d}"))[0]


def download(library, storage, v, size, name=None):
    f = storage.layout.videos / (name or f"{v.id}.mp4")
    f.write_bytes(b"0" * size)
    return library.attach_local_file(v.id, f, "720p")


# ---------- resumo, maiores, verificação ----------
def test_summary_largest_and_verify(env):
    maint, library, storage, provider = env
    a, b, c = (video(library, provider, i) for i in (1, 2, 3))
    download(library, storage, a, 500)
    download(library, storage, b, 3000)
    s = maint.summary()
    assert (s["videos"], s["video_files"], s["videos_bytes"]) == (3, 2, 3500) and s["free"] > 0
    assert [(e.video.id, e.size) for e in maint.largest()] == [(b.id, 3000), (a.id, 500)]
    assert maint.largest(limit=1)[0].video.id == b.id
    (storage.layout.videos / f"{a.id}.mp4").unlink()
    counts = maint.verify_all()
    assert counts == {"downloaded": 1, "missing": 1, "invalid": 0, "saved": 1}
    assert [v.id for v in maint.problems()] == [a.id]


def test_free_space_deletes_only_selected_files_and_keeps_records(env):
    maint, library, storage, provider = env
    a, b = video(library, provider, 1), video(library, provider, 2)
    download(library, storage, a, 700)
    download(library, storage, b, 300)
    assert maint.free_space_of([a.id]) == 700
    assert not (storage.layout.videos / f"{a.id}.mp4").exists() and (storage.layout.videos / f"{b.id}.mp4").exists()
    assert library.get(a.id).local_status == "none" and library.get(a.id).title == "V1"


# ---------- arquivos soltos ----------
def test_find_and_delete_orphans_safely(env, tmp_path):
    maint, library, storage, provider = env
    a = video(library, provider, 1)
    download(library, storage, a, 100)
    loose = storage.layout.videos / "sub" / "solto.mkv"
    loose.parent.mkdir()
    loose.write_bytes(b"0" * 900)
    (storage.layout.videos / "notas.txt").write_text("não é vídeo")
    orphans = maint.find_orphans()
    assert [(o.path.name, o.size) for o in orphans] == [("solto.mkv", 900)]
    outside = tmp_path / "fora.mp4"
    outside.write_bytes(b"x")
    with pytest.raises(StorageError) as exc:
        maint.delete_orphan(outside)
    assert exc.value.code == "path_escapes_root" and outside.exists()
    with pytest.raises(StorageError) as exc:
        maint.delete_orphan(storage.layout.videos / f"{a.id}.mp4")  # em uso por um registro
    assert exc.value.code == "not_orphan" and (storage.layout.videos / f"{a.id}.mp4").exists()
    assert maint.delete_orphan(loose) == 900 and not loose.exists() and (storage.layout.videos / "notas.txt").exists()


# ---------- localizar de novo ----------
needs_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg não instalado")


@needs_ffmpeg
def test_relocate_links_a_valid_file_moved_by_the_user(env, tmp_path):
    maint, library, storage, provider = env
    media = make_media(tmp_path / "media")
    tools = FFmpegTools(FFMPEG, FFPROBE).check()
    v = video(library, provider, 1)
    download(library, storage, v, 100)
    (storage.layout.videos / f"{v.id}.mp4").unlink()
    library.validate_all()
    assert library.get(v.id).local_status == "missing"
    moved = tmp_path / "outro-disco" / "meu.mp4"
    moved.parent.mkdir()
    moved.write_bytes(media["progressive_mp4"].read_bytes())
    got = maint.relocate(v.id, moved, tools)
    assert got.local_status == "ok" and got.local_path == str(moved)  # fora da biblioteca: caminho absoluto
    assert library.is_inside_library(moved) is False
    assert library.delete_local_file(v.id) == 0 and moved.exists()  # e nunca é apagado pelo app


@needs_ffmpeg
def test_relocate_inside_library_is_stored_relative(env, tmp_path):
    maint, library, storage, provider = env
    media = make_media(tmp_path / "media")
    tools = FFmpegTools(FFMPEG, FFPROBE).check()
    v = video(library, provider, 1)
    inside = storage.layout.videos / "novo.mp4"
    inside.write_bytes(media["progressive_mp4"].read_bytes())
    assert maint.relocate(v.id, inside, tools).local_path == "novo.mp4"


@needs_ffmpeg
def test_relocate_rejects_bad_files(env, tmp_path):
    maint, library, storage, provider = env
    media = make_media(tmp_path / "media")
    tools = FFmpegTools(FFMPEG, FFPROBE).check()
    a, b = video(library, provider, 1), video(library, provider, 2)
    with pytest.raises(StorageError) as exc:
        maint.relocate(a.id, tmp_path / "nao_existe.mp4", tools)
    assert exc.value.code == "relocate_invalid"
    txt = tmp_path / "x.txt"
    txt.write_text("oi")
    with pytest.raises(StorageError):
        maint.relocate(a.id, txt, tools)
    garbage = tmp_path / "lixo.mp4"
    garbage.write_bytes(media["garbage"].read_bytes())
    with pytest.raises(MediaError) as exc2:
        maint.relocate(a.id, garbage, tools)
    assert exc2.value.code == "invalid_media" and library.get(a.id).local_status == "none"
    audio_only = tmp_path / "som.mp4"
    audio_only.write_bytes(media["audio_aac"].read_bytes())
    with pytest.raises(MediaError):
        maint.relocate(a.id, audio_only, tools)
    good = tmp_path / "bom.mp4"
    good.write_bytes(media["progressive_mp4"].read_bytes())
    maint.relocate(a.id, good, tools)
    with pytest.raises(StorageError) as exc3:
        maint.relocate(b.id, good, tools)  # o mesmo arquivo para dois vídeos
    assert exc3.value.code == "relocate_in_use"
    with pytest.raises(StorageError):
        maint.relocate(999, good, tools)


# ---------- miniaturas e metadados ----------
def test_clear_thumbnail_cache(env, qtbot):
    maint, library, storage, provider = env
    (storage.layout.thumbnails / "a.jpg").write_bytes(b"x" * 10)
    (storage.layout.thumbnails / "b.jpg").write_bytes(b"x" * 30)
    with qtbot.waitSignal(library.changed):
        assert maint.clear_thumbnail_cache() == (2, 40)
    assert list(storage.layout.thumbnails.iterdir()) == []


def test_refresh_metadata_updates_fields_and_survives_failures(env):
    maint, library, storage, provider = env
    a, b = video(library, provider, 1), video(library, provider, 2)
    provider.title = "Título novo"
    seen = []
    result = maint.refresh_metadata(progress=lambda done, total: seen.append((done, total)))
    assert result.updated == 2 and result.failed == () and seen[0] == (0, 2) and seen[-1] == (2, 2)
    assert library.get(a.id).title == "Título novo" and library.get(a.id).channel == "Canal Teste"
    provider.error = "private"
    result = maint.refresh_metadata([a.id])
    assert result.updated == 0 and result.failed == ((a.id, "private"),) and library.get(a.id).title == "Título novo"


def test_refresh_only_selected_ids(env):
    maint, library, storage, provider = env
    a, b = video(library, provider, 1), video(library, provider, 2)
    provider.title = "X"
    maint.refresh_metadata([b.id])
    assert library.get(a.id).title == "V1" and library.get(b.id).title == "X"


# ---------- provedores ----------
def test_installed_versions_has_both_providers():
    versions = ps.installed_versions()
    assert set(versions) == {"pytubefix", "ytdlp"}


def test_update_runs_pip_and_redacts_output():
    calls = []

    def runner(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="Successfully installed yt-dlp token=SEGREDO", stderr="")

    result = ps.update_providers(runner=runner, frozen=False)
    assert result.ok and "SEGREDO" not in result.output
    assert calls[0][1:4] == ["-m", "pip", "install"] and "--upgrade" in calls[0] and "pytubefix" in calls[0] and "yt-dlp" in calls[0]


def test_update_failure_timeout_and_frozen_app():
    fail = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="erro de rede")
    assert (ps.update_providers(runner=fail, frozen=False).ok, ps.update_providers(runner=fail, frozen=False).code) == (False, "failed")

    def slow(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)

    assert ps.update_providers(runner=slow, frozen=False).code == "timeout"

    def nopip(cmd, **kw):
        raise FileNotFoundError("sem python")

    assert ps.update_providers(runner=nopip, frozen=False).code == "no_pip"
    never = lambda cmd, **kw: pytest.fail("não deve rodar pip no executável empacotado")
    result = ps.update_providers(runner=never, frozen=True)
    assert not result.ok and result.code == "frozen" and ps.can_self_update(frozen=True) is False


# ---------- diagnóstico ----------
def test_diagnostics_has_no_secrets_urls_or_username(env, settings, tmp_path):
    maint, library, storage, provider = env
    chain = ProviderChain([provider])
    video(library, provider, 1)
    from app.logging_setup import LOG_NAME

    storage.layout.logs.mkdir(exist_ok=True)
    home = tmp_path / "usuario-secreto"
    (storage.layout.logs / LOG_NAME).write_text(f"erro em {home}/x token=ABC123\nGET https://a.googlevideo.com/v?sig=ULTRA\n", encoding="utf-8")
    text = dg.build_report(settings, storage, library, tools=None, providers=chain, home=home)
    assert "ABC123" not in text and "ULTRA" not in text and "usuario-secreto" not in text
    assert "DinoTube" in text and "vídeos: 1" in text and "ffmpeg: não encontrado" in text and "ordem: f" in text
    assert "~" in text


def test_scrub_paths_only_replaces_the_home_folder():
    assert dg.scrub_paths("/home/ana/videos/a.mp4 e /outra/pasta", home="/home/ana") == "~/videos/a.mp4 e /outra/pasta"
    assert dg.scrub_paths("texto", home="/") == "texto"
