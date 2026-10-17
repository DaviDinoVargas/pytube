import sys
import threading
import types
from pathlib import Path

import pytest

from app.infrastructure.providers import quality
from app.infrastructure.providers import pytubefix_provider as pf
from app.infrastructure.providers import ytdlp_provider as yd
from app.infrastructure.providers.base import DownloadCancelled, ProviderError, StreamOption
from app.infrastructure.providers.chain import ProviderChain
from tests.fakes import VID, FakeProvider, default_streams


# ---------- qualidade ----------
def test_available_heights_need_audio_for_adaptive():
    streams = default_streams()
    assert quality.available_heights(streams) == [2160, 1080, 720, 360]
    no_audio = [s for s in streams if s.kind != "audio"]
    assert quality.available_heights(no_audio) == [720, 360]  # só os progressivos


def test_pick_prefers_progressive_when_it_exists():
    sel = quality.pick(default_streams(), 720)
    assert sel.mode == "direct" and sel.video.format_id == "22" and sel.audio is None


def test_pick_merges_adaptive_and_prefers_mp4_h264_with_higher_fps():
    sel = quality.pick(default_streams(), 1080)
    assert sel.mode == "merge"
    assert sel.video.format_id == "299"  # mp4/avc1 a 60 fps vence o webm/vp9
    assert sel.audio.format_id == "140"  # m4a vence opus
    assert not quality.needs_recode(sel)


def test_pick_vp9_only_needs_recode():
    sel = quality.pick(default_streams(), 2160)
    assert sel.video.format_id == "313" and quality.needs_recode(sel)


def test_pick_unknown_height_raises():
    with pytest.raises(ProviderError) as exc:
        quality.pick(default_streams(), 480)
    assert exc.value.code == "unsupported"


def test_pick_adaptive_without_audio_is_unsupported():
    streams = [s for s in default_streams() if s.kind != "audio"]
    with pytest.raises(ProviderError):
        quality.pick(streams, 1080)


def test_default_height_follows_player():
    streams = default_streams()
    assert quality.default_height(streams) == 2160
    assert quality.default_height(streams, 1080) == 1080
    assert quality.default_height(streams, 900) == 720  # mais próxima abaixo
    assert quality.default_height(streams, 100) == 360  # nada abaixo: menor disponível
    assert quality.default_height([]) is None


def test_stream_label_shows_high_fps():
    assert StreamOption("video", "1", height=1080, fps=60).label == "1080p60"
    assert StreamOption("video", "1", height=1080, fps=30).label == "1080p"


def test_equivalent_stream_across_providers():
    a = StreamOption("video", "299", "mp4", 1080, 60, vcodec="avc1")
    other = [StreamOption("video", "x1", "mp4", 1080, 30, vcodec="avc1"), StreamOption("audio", "x2")]
    assert quality.equivalent(a, other).format_id == "x1"
    assert quality.equivalent(a, [StreamOption("video", "x3", "mp4", 720)]) is None


# ---------- cadeia de provedores ----------
def test_chain_uses_configured_order_and_falls_back():
    a = FakeProvider("a", error="failed")
    b = FakeProvider("b", title="do B")
    chain = ProviderChain([a, b], order=("a", "b"))
    assert chain.fetch_info(VID).title == "do B"
    chain.order = ("b", "a")
    assert chain.fetch_info(VID).provider == "b"
    assert a.fetch_calls == 1  # não foi consultado de novo


def test_chain_stops_on_terminal_error():
    a = FakeProvider("a", error="private")
    b = FakeProvider("b")
    with pytest.raises(ProviderError) as exc:
        ProviderChain([a, b], order=("a", "b")).fetch_info(VID)
    assert exc.value.code == "private" and b.fetch_calls == 0


def test_chain_reports_most_specific_error_when_all_fail():
    chain = ProviderChain([FakeProvider("a", error="failed"), FakeProvider("b", error="unavailable")])
    with pytest.raises(ProviderError) as exc:
        chain.fetch_info(VID)
    assert exc.value.code == "unavailable"


def test_chain_skips_unavailable_providers_and_reports_when_none():
    chain = ProviderChain([FakeProvider("a", available=False)])
    with pytest.raises(ProviderError) as exc:
        chain.fetch_info(VID)
    assert exc.value.code == "not_installed"
    assert ProviderChain([FakeProvider("a", available=False), FakeProvider("b")]).fetch_info(VID).provider == "b"


def test_chain_unknown_names_in_order_are_ignored():
    chain = ProviderChain([FakeProvider("a"), FakeProvider("b")], order=("zzz", "b"))
    assert chain.order == ("b", "a")


def test_download_falls_back_to_other_provider_with_equivalent_stream(tmp_path):
    a = FakeProvider("a", download_error="failed")
    b = FakeProvider("b")
    chain = ProviderChain([a, b], order=("a", "b"))
    info = chain.fetch_info(VID)
    stream = quality.pick(info.streams, 720).video
    seen = []
    used = chain.download(info, stream, tmp_path / "x.mp4", lambda d, t: seen.append(d), threading.Event())
    assert used == "b" and (tmp_path / "x.mp4").stat().st_size == 4096 and seen[-1] == 4096


def test_download_cancel_is_not_retried(tmp_path):
    a, b = FakeProvider("a"), FakeProvider("b")
    chain = ProviderChain([a, b], order=("a", "b"))
    info = chain.fetch_info(VID)
    event = threading.Event()
    event.set()
    with pytest.raises(DownloadCancelled):
        chain.download(info, info.streams[1], tmp_path / "x.mp4", lambda d, t: None, event)
    assert b.downloads == []


def test_download_terminal_error_stops(tmp_path):
    a = FakeProvider("a", download_error="drm")
    b = FakeProvider("b")
    chain = ProviderChain([a, b], order=("a", "b"))
    info = chain.fetch_info(VID)
    with pytest.raises(ProviderError) as exc:
        chain.download(info, info.streams[1], tmp_path / "x.mp4", lambda d, t: None, threading.Event())
    assert exc.value.code == "drm" and b.downloads == []


# ---------- mapeamento de erros ----------
@pytest.mark.parametrize("cls,code", [
    ("VideoPrivate", "private"), ("MembersOnly", "members_only"), ("AgeRestrictedError", "age_restricted"),
    ("LiveStreamError", "live"), ("VideoUnavailable", "unavailable"), ("Whatever", "failed"),
])
def test_pytubefix_error_mapping(cls, code):
    assert pf.map_error(type(cls, (Exception,), {})("x")).code == code


def test_pytubefix_network_errors():
    assert pf.map_error(ConnectionError("x")).code == "network"
    assert pf.map_error(Exception("<urlopen error [Errno -3]>")).code == "network"


@pytest.mark.parametrize("msg,code", [
    ("ERROR: Private video. Sign in", "private"),
    ("Sign in to confirm your age", "age_restricted"),
    ("This video is DRM protected", "drm"),
    ("Video unavailable", "unavailable"),
    ("Sign in to confirm you’re not a bot", "blocked"),
    ("<urlopen error timed out>", "network"),
    ("algo inesperado", "failed"),
])
def test_ytdlp_error_mapping(msg, code):
    assert yd.map_error(Exception(msg)).code == code


# ---------- adaptadores (com módulos simulados) ----------
class _PfStream:
    def __init__(self, itag, res, progressive, video, audio, subtype="mp4", fps=30, abr=None, size=1000):
        self.itag, self.resolution, self.is_progressive = itag, res, progressive
        self.includes_video_track = video
        self.subtype, self.fps, self.abr = subtype, fps, abr
        self.filesize_approx = size
        self.video_codec = "avc1.640028" if video else None
        self.audio_codec = "mp4a.40.2" if audio else None
        self.filesize = size


def test_pytubefix_provider_maps_streams(monkeypatch):
    streams = [
        _PfStream(22, "720p", True, True, True),
        _PfStream(137, "1080p", False, True, False),
        _PfStream(140, None, False, False, True, subtype="m4a", abr="128kbps"),
    ]

    class FakeYT:
        title, author, length, thumbnail_url, description = "T", "Canal", 99, "https://i.ytimg.com/a.jpg", "D"

        def __init__(self, url, on_progress_callback=None):
            self.streams = streams

    monkeypatch.setitem(sys.modules, "pytubefix", types.SimpleNamespace(YouTube=FakeYT))
    p = pf.PytubefixProvider()
    info = p.fetch_info(VID)
    assert (info.title, info.channel, info.duration, info.provider) == ("T", "Canal", 99, "pytubefix")
    kinds = {s.format_id: s for s in info.streams}
    assert kinds["22"].kind == "progressive" and kinds["22"].height == 720
    assert kinds["137"].kind == "video" and kinds["137"].height == 1080
    assert kinds["140"].kind == "audio" and kinds["140"].bitrate == 128 and kinds["140"].height is None


def test_pytubefix_provider_maps_exceptions(monkeypatch):
    class VideoPrivate(Exception):
        pass

    class Boom:
        def __init__(self, *a, **k):
            raise VideoPrivate("privado")

    monkeypatch.setitem(sys.modules, "pytubefix", types.SimpleNamespace(YouTube=Boom))
    with pytest.raises(ProviderError) as exc:
        pf.PytubefixProvider().fetch_info(VID)
    assert exc.value.code == "private"


def test_pytubefix_download_reports_progress_and_cancels(monkeypatch, tmp_path):
    class Target:
        filesize = 100

        def download(self, output_path, filename):
            for remaining in (75, 50, 25, 0):
                self.cb(self, b"", remaining)
            (Path(output_path) / filename).write_bytes(b"x")

    target = Target()

    class FakeYT:
        def __init__(self, url, on_progress_callback=None):
            target.cb = on_progress_callback
            self.streams = types.SimpleNamespace(get_by_itag=lambda itag: target)

    monkeypatch.setitem(sys.modules, "pytubefix", types.SimpleNamespace(YouTube=FakeYT))
    p = pf.PytubefixProvider()
    seen = []
    p.download_stream(VID, StreamOption("progressive", "22"), tmp_path / "a.mp4", lambda d, t: seen.append((d, t)), threading.Event())
    assert seen == [(25, 100), (50, 100), (75, 100), (100, 100)]
    event = threading.Event()
    event.set()
    with pytest.raises(DownloadCancelled):
        p.download_stream(VID, StreamOption("progressive", "22"), tmp_path / "b.mp4", lambda d, t: None, event)


def test_ytdlp_provider_maps_formats_and_blocks_live(monkeypatch):
    data = {
        "title": "T", "uploader": "Canal", "duration": 120, "thumbnail": "https://i.ytimg.com/a.jpg", "description": "D",
        "formats": [
            {"format_id": "18", "ext": "mp4", "height": 360, "fps": 30, "vcodec": "avc1", "acodec": "mp4a", "tbr": 500},
            {"format_id": "137", "ext": "mp4", "height": 1080, "fps": 60, "vcodec": "avc1", "acodec": "none", "tbr": 4000, "filesize": 9},
            {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a", "abr": 128.0},
            {"format_id": "sb0", "ext": "mhtml", "vcodec": "none", "acodec": "none"},
        ],
    }

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            return data

    monkeypatch.setitem(sys.modules, "yt_dlp", types.SimpleNamespace(YoutubeDL=FakeYDL))
    info = yd.YtdlpProvider().fetch_info(VID)
    assert [s.format_id for s in info.streams] == ["18", "137", "140"]  # a faixa de storyboard é ignorada
    by = {s.format_id: s for s in info.streams}
    assert by["137"].kind == "video" and by["137"].fps == 60 and by["137"].filesize == 9
    assert by["140"].kind == "audio" and by["140"].bitrate == 128
    data["is_live"] = True
    with pytest.raises(ProviderError) as exc:
        yd.YtdlpProvider().fetch_info(VID)
    assert exc.value.code == "live"


def test_ytdlp_download_escapes_percent_and_handles_cancel(monkeypatch, tmp_path):
    captured = {}

    class FakeYDL:
        def __init__(self, opts):
            captured.update(opts)
            self.hook = opts["progress_hooks"][0]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def download(self, urls):
            self.hook({"status": "downloading", "downloaded_bytes": 50, "total_bytes": 100})
            self.hook({"status": "downloading", "downloaded_bytes": 100, "total_bytes_estimate": 100})

    monkeypatch.setitem(sys.modules, "yt_dlp", types.SimpleNamespace(YoutubeDL=FakeYDL))
    seen = []
    yd.YtdlpProvider().download_stream(VID, StreamOption("video", "137"), tmp_path / "100%.mp4", lambda d, t: seen.append((d, t)), threading.Event())
    assert seen == [(50, 100), (100, 100)]
    assert captured["outtmpl"].endswith("100%%.mp4") and captured["format"] == "137"
    event = threading.Event()
    event.set()
    with pytest.raises(DownloadCancelled):
        yd.YtdlpProvider().download_stream(VID, StreamOption("video", "137"), tmp_path / "c.mp4", lambda d, t: None, event)


def test_providers_report_not_installed(monkeypatch):
    monkeypatch.setattr(pf.PytubefixProvider, "is_available", lambda self: False)
    with pytest.raises(ProviderError) as exc:
        pf.PytubefixProvider().fetch_info(VID)
    assert exc.value.code == "not_installed"
