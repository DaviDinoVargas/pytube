"""Provedores simulados: os testes nunca dependem do YouTube real."""

import threading

from app.infrastructure.providers.base import (
    DownloadCancelled,
    ProviderError,
    StreamOption,
    VideoInfo,
    VideoProvider,
)

VID = "dQw4w9WgXcQ"


def default_streams():
    return [
        StreamOption("progressive", "18", "mp4", 360, 30, 96, 5_000_000, "avc1.42001E", "mp4a.40.2"),
        StreamOption("progressive", "22", "mp4", 720, 30, 192, 20_000_000, "avc1.64001F", "mp4a.40.2"),
        StreamOption("video", "137", "mp4", 1080, 30, 4000, 80_000_000, "avc1.640028"),
        StreamOption("video", "248", "webm", 1080, 30, 3000, 60_000_000, "vp9"),
        StreamOption("video", "299", "mp4", 1080, 60, 6000, 120_000_000, "avc1.64002a"),
        StreamOption("video", "313", "webm", 2160, 30, 12000, 300_000_000, "vp9"),
        StreamOption("audio", "140", "m4a", None, None, 128, 3_000_000, "", "mp4a.40.2"),
        StreamOption("audio", "251", "webm", None, None, 160, 3_500_000, "", "opus"),
    ]


class FakeProvider(VideoProvider):
    def __init__(self, name="fake", streams=None, title="Vídeo de teste", error=None, download_error=None,
                 available=True, payload=b"0" * 4096):
        self.name = name
        self._streams = default_streams() if streams is None else streams
        self.title = title
        self.error = error
        self.download_error = download_error
        self._available = available
        self.payload = payload
        self.fetch_calls = 0
        self.downloads = []
        self.url_error = None
        self.url_template = "https://rr1---sn-abc.googlevideo.com/videoplayback?id={id}&itag={itag}"

    def is_available(self):
        return self._available

    def fetch_info(self, video_id):
        self.fetch_calls += 1
        if self.error:
            raise ProviderError(self.error, "simulado")
        return VideoInfo(
            source_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
            title=self.title,
            channel="Canal Teste",
            duration=212,
            thumbnail_url="https://i.ytimg.com/vi/x/hq.jpg",
            description="Descrição de teste",
            provider=self.name,
            streams=list(self._streams),
        )

    def stream_url(self, video_id, stream):
        if self.url_error:
            raise ProviderError(self.url_error, "simulado")
        return self.url_template.format(id=video_id, itag=stream.format_id)

    def download_stream(self, video_id, stream, dest, on_progress, cancel_event):
        self.downloads.append((video_id, stream.format_id))
        if self.download_error:
            raise ProviderError(self.download_error, "simulado")
        total = len(self.payload)
        step = max(1, total // 4)
        written = 0
        with open(dest, "wb") as fh:
            while written < total:
                if cancel_event.is_set():
                    raise DownloadCancelled()
                chunk = self.payload[written:written + step]
                fh.write(chunk)
                written += len(chunk)
                on_progress(written, total)


class MediaProvider(FakeProvider):
    """Entrega arquivos de mídia reais (gerados pelo ffmpeg) para os testes de download.

    `files` mapeia format_id -> caminho. `delay` espera entre os blocos (para testar cancelamento e
    concorrência). `fail_times` faz as primeiras N tentativas de download falharem.
    """

    def __init__(self, files, streams, name="media", duration=2, delay=0.0, fail_times=0, fail_code="failed", **kw):
        super().__init__(name, streams=streams, **kw)
        self.files = files
        self.duration = duration
        self.delay = delay
        self.fail_times = fail_times
        self.fail_code = fail_code
        self.running = 0
        self.max_running = 0
        self._guard = threading.Lock()

    def fetch_info(self, video_id):
        info = super().fetch_info(video_id)
        info.duration = self.duration
        return info

    def download_stream(self, video_id, stream, dest, on_progress, cancel_event):
        import time

        with self._guard:
            self.running += 1
            self.max_running = max(self.max_running, self.running)
            self.downloads.append((video_id, stream.format_id))
        try:
            if self.fail_times > 0:
                self.fail_times -= 1
                raise ProviderError(self.fail_code, "simulado")
            data = self.files[stream.format_id].read_bytes()
            total, step, written = len(data), max(1, len(data) // 5), 0
            with open(dest, "wb") as fh:
                while written < total:
                    if cancel_event.is_set():
                        raise DownloadCancelled()
                    chunk = data[written:written + step]
                    fh.write(chunk)
                    written += len(chunk)
                    on_progress(written, total)
                    if self.delay:
                        time.sleep(self.delay)
        finally:
            with self._guard:
                self.running -= 1


def _stub_player_class():
    from app.ui.player.base import PlayerBackend

    class StubPlayer(PlayerBackend):
        """Motor de reprodução falso: registra os comandos e deixa o teste emitir os eventos."""

        def __init__(self, can_quality=False):
            super().__init__()
            self.calls = []
            self._can_quality = can_quality
            self._playing = False
            self._pos = 0.0
            self._dur = 0.0

        def _log(self, name, *args):
            self.calls.append((name, *args))

        def load_file(self, path, start=0.0, autoplay=True):
            self._log("load_file", str(path), start)
            self._playing = autoplay

        def load_url(self, url, start=0.0, autoplay=True):
            self._log("load_url", url, start)
            self._playing = autoplay

        def load(self, video_id, start=0.0):
            self._log("load", video_id, start)

        def play(self):
            self._log("play")
            self._playing = True
            self.state_changed.emit(True)

        def pause(self):
            self._log("pause")
            if self._playing:
                self._playing = False
                self.state_changed.emit(False)

        def stop(self):
            self._log("stop")
            self._playing = False

        def shutdown(self):
            self._log("shutdown")

        def seek(self, seconds):
            self._log("seek", seconds)
            self._pos = seconds

        def set_volume(self, percent):
            self._log("volume", percent)

        def set_muted(self, muted):
            self._log("muted", muted)

        def set_rate(self, rate):
            self._log("rate", rate)

        def set_quality(self, height):
            self._log("quality", height)

        def can_change_quality(self):
            return self._can_quality

        def position(self):
            return self._pos

        def duration(self):
            return self._dur

        def is_playing(self):
            return self._playing

        def names(self):
            return [c[0] for c in self.calls]

    return StubPlayer


def make_stub_player(**kwargs):
    return _stub_player_class()(**kwargs)
