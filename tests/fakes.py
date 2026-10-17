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
