import threading
import time

import pytest

from app.infrastructure.media import ffmpeg as ff
from app.infrastructure.media.ffmpeg import FFmpegTools, MediaError, MergeCancelled, locate, parse_version, version_is_supported
from app.infrastructure.providers import quality
from app.infrastructure.providers.base import StreamOption
from tests.media import FFMPEG, FFPROBE, HAS_FFMPEG, make_media

needs_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg não instalado")


@pytest.mark.parametrize("text,expected", [
    ("ffmpeg version 6.1.1-3ubuntu5 Copyright", ("release", (6, 1))),
    ("ffmpeg version n7.0.2 Copyright", ("release", (7, 0))),
    ("ffmpeg version 9.0.2 Copyright", ("release", (9, 0))),
    ("ffmpeg version 2025-08-25-git-1b62f9d3ae-essentials_build-www.gyan.dev", ("date", 2025)),
    ("ffmpeg version N-12345-gabcdef", None),
    ("", None),
])
def test_parse_version(text, expected):
    assert parse_version(text) == expected


@pytest.mark.parametrize("parsed,ok", [
    (("release", (4, 4)), True), (("release", (3, 4)), False), (("release", (9, 0)), True),
    (("date", 2025), True), (("date", 2019), False), (None, True),
])
def test_version_support(parsed, ok):
    assert version_is_supported(parsed) is ok


def test_locate_prefers_override_then_bundled_then_system(tmp_path, monkeypatch):
    exe = ".exe" if ff.sys.platform == "win32" else ""
    bundled = tmp_path / "root" / "third_party" / "ffmpeg" / "bin"
    bundled.mkdir(parents=True)
    for n in ("ffmpeg", "ffprobe"):
        (bundled / f"{n}{exe}").write_text("x")
    custom = tmp_path / "custom"
    custom.mkdir()
    for n in ("ffmpeg", "ffprobe"):
        (custom / f"{n}{exe}").write_text("x")
    assert locate(tmp_path / "root").ffmpeg == str(bundled / f"ffmpeg{exe}")
    assert locate(tmp_path / "root", override=custom).ffmpeg == str(custom / f"ffmpeg{exe}")
    assert locate(tmp_path / "root", override=custom / f"ffmpeg{exe}").ffmpeg == str(custom / f"ffmpeg{exe}")  # arquivo também vale
    assert locate(tmp_path / "root", override=tmp_path / "nao_existe").ffmpeg == str(bundled / f"ffmpeg{exe}")
    monkeypatch.setattr(ff.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert locate(tmp_path / "vazio").ffmpeg == "/usr/bin/ffmpeg"
    monkeypatch.setattr(ff.shutil, "which", lambda name: None)
    assert locate(tmp_path / "vazio") is None


def test_check_reports_missing_binary(tmp_path):
    with pytest.raises(MediaError) as exc:
        FFmpegTools(tmp_path / "nao_existe", tmp_path / "nem_este").check()
    assert exc.value.code == "ffmpeg_missing"


@needs_ffmpeg
def test_check_accepts_real_ffmpeg():
    tools = FFmpegTools(FFMPEG, FFPROBE).check()
    assert tools.version_text.startswith("ffmpeg version")


def test_merge_command_copies_or_recodes_per_stream():
    copy = FFmpegTools.merge_command("ff", "v", "a", "o", True, True)
    assert copy[copy.index("-c:v") + 1] == "copy" and copy[copy.index("-c:a") + 1] == "copy"
    both = FFmpegTools.merge_command("ff", "v", "a", "o", False, False)
    assert "libx264" in both and "aac" in both and "yuv420p" in both
    mixed = FFmpegTools.merge_command("ff", "v", "a", "o", True, False)
    assert mixed[mixed.index("-c:v") + 1] == "copy" and mixed[mixed.index("-c:a") + 1] == "aac"
    assert "-movflags" in copy and "+faststart" in copy and copy[-2:] == ["mp4", "o"] or copy[-1] == "o"


def test_recode_plan_per_stream():
    h264 = StreamOption("video", "1", "mp4", 1080, vcodec="avc1.640028")
    vp9 = StreamOption("video", "2", "webm", 1080, vcodec="vp9")
    aac = StreamOption("audio", "3", "m4a", acodec="mp4a.40.2")
    opus = StreamOption("audio", "4", "webm", acodec="opus")
    S = quality.Selection
    assert quality.recode_plan(S(1080, h264, aac)) == (True, True)
    assert quality.recode_plan(S(1080, h264, opus)) == (True, False)
    assert quality.recode_plan(S(1080, vp9, aac)) == (False, True)
    assert quality.recode_plan(S(1080, vp9, opus)) == (False, False)
    assert quality.recode_plan(S(720, StreamOption("progressive", "5", "mp4", 720, vcodec="avc1"))) == (True, True)


@needs_ffmpeg
def test_probe_real_files(tmp_path):
    media = make_media(tmp_path)
    tools = FFmpegTools(FFMPEG, FFPROBE)
    p = tools.probe(media["progressive_mp4"])
    assert p.has_video and p.has_audio and p.vcodec == "h264" and 1.5 < p.duration < 3 and (p.width, p.height) == (320, 180)
    assert tools.probe(media["audio_aac"]).has_video is False
    assert tools.probe(media["video_h264"]).has_audio is False


@needs_ffmpeg
def test_probe_rejects_garbage_and_missing(tmp_path):
    media = make_media(tmp_path)
    tools = FFmpegTools(FFMPEG, FFPROBE)
    for bad in (media["garbage"], tmp_path / "nao_existe.mp4"):
        with pytest.raises(MediaError) as exc:
            tools.probe(bad)
        assert exc.value.code == "invalid_media"


@needs_ffmpeg
def test_merge_copy_h264_aac_without_recoding(tmp_path):
    media = make_media(tmp_path)
    tools = FFmpegTools(FFMPEG, FFPROBE)
    out = tmp_path / "out.mp4"
    seen = []
    tools.merge(media["video_h264"], media["audio_aac"], out, True, True, duration=2, on_progress=seen.append)
    info = tools.probe(out)
    assert info.has_video and info.has_audio and (info.vcodec, info.acodec) == ("h264", "aac") and 1.5 < info.duration < 3
    assert not seen or max(seen) <= 1.0


@needs_ffmpeg
def test_merge_vp9_opus_recodes_into_playable_h264_aac(tmp_path):
    media = make_media(tmp_path)
    tools = FFmpegTools(FFMPEG, FFPROBE)
    out = tmp_path / "out.mp4"
    tools.merge(media["video_vp9"], media["audio_opus"], out, False, False, duration=2)
    info = tools.probe(out)
    assert (info.vcodec, info.acodec) == ("h264", "aac") and info.has_video and info.has_audio


@needs_ffmpeg
def test_merge_failure_raises_and_leaves_no_output(tmp_path):
    media = make_media(tmp_path)
    tools = FFmpegTools(FFMPEG, FFPROBE)
    out = tmp_path / "out.mp4"
    with pytest.raises(MediaError) as exc:
        tools.merge(media["garbage"], media["audio_aac"], out)
    assert exc.value.code == "merge_failed" and not out.exists()


@needs_ffmpeg
def test_merge_can_be_cancelled(tmp_path):
    media = make_media(tmp_path, seconds=2)
    tools = FFmpegTools(FFMPEG, FFPROBE)
    out = tmp_path / "out.mp4"
    event = threading.Event()
    event.set()
    with pytest.raises(MergeCancelled):
        tools.merge(media["video_vp9"], media["audio_opus"], out, False, False, duration=2, cancel_event=event)
    assert not out.exists()
