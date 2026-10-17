import re

from app.infrastructure.providers.base import (
    DownloadCancelled,
    ProviderError,
    StreamOption,
    VideoInfo,
    VideoProvider,
    module_installed,
)

_BY_CLASS = {
    "VideoPrivate": "private",
    "MembersOnly": "members_only",
    "AgeRestrictedError": "age_restricted",
    "AgeCheckRequiredError": "age_restricted",
    "LiveStreamError": "live",
    "VideoUnavailable": "unavailable",
    "VideoRegionBlocked": "unavailable",
    "MaxRetriesExceeded": "network",
    "BotDetection": "blocked",
}
_NETWORK_HINTS = ("urlopen", "timed out", "getaddrinfo", "connection", "network", "name resolution")


def map_error(exc):
    """Traduz uma exceção do pytubefix para um ProviderError com código estável."""
    if isinstance(exc, (DownloadCancelled, ProviderError)):
        return exc
    code = _BY_CLASS.get(type(exc).__name__)
    if code is None:
        text = str(exc).lower()
        if isinstance(exc, (ConnectionError, TimeoutError)) or any(h in text for h in _NETWORK_HINTS):
            code = "network"
        else:
            code = "failed"
    return ProviderError(code, str(exc)[:300])


def _height(resolution):
    match = re.match(r"(\d+)p", resolution or "")
    return int(match.group(1)) if match else None


def _safe(getter):
    try:
        return getter()
    except Exception:
        return None


def to_option(stream):
    if getattr(stream, "is_progressive", False):
        kind = "progressive"
    elif getattr(stream, "includes_video_track", False):
        kind = "video"
    else:
        kind = "audio"
    abr = _safe(lambda: stream.abr)
    return StreamOption(
        kind=kind,
        format_id=str(stream.itag),
        ext=getattr(stream, "subtype", "") or "mp4",
        height=_height(getattr(stream, "resolution", None)),
        fps=getattr(stream, "fps", None) if kind != "audio" else None,
        bitrate=int(abr.replace("kbps", "")) if isinstance(abr, str) and abr.replace("kbps", "").isdigit() else None,
        filesize=_safe(lambda: stream.filesize_approx),
        vcodec=_safe(lambda: stream.video_codec) or "",
        acodec=_safe(lambda: stream.audio_codec) or "",
    )


class PytubefixProvider(VideoProvider):
    name = "pytubefix"

    def is_available(self):
        return module_installed("pytubefix")

    def _youtube(self, video_id, on_progress=None):
        from pytubefix import YouTube  # importação tardia: o app abre mesmo sem o pacote

        return YouTube(f"https://www.youtube.com/watch?v={video_id}", on_progress_callback=on_progress)

    def fetch_info(self, video_id):
        if not self.is_available():
            raise ProviderError("not_installed", self.name)
        try:
            yt = self._youtube(video_id)
            streams = [to_option(s) for s in yt.streams]
            return VideoInfo(
                source_id=video_id,
                url=f"https://www.youtube.com/watch?v={video_id}",
                title=yt.title or "",
                channel=yt.author or "",
                duration=yt.length,
                thumbnail_url=yt.thumbnail_url or "",
                description=_safe(lambda: yt.description) or "",
                provider=self.name,
                streams=streams,
            )
        except Exception as exc:
            raise map_error(exc) from exc

    def download_stream(self, video_id, stream, dest, on_progress, cancel_event):
        if not self.is_available():
            raise ProviderError("not_installed", self.name)

        def callback(s, _chunk, remaining):
            if cancel_event.is_set():
                raise DownloadCancelled()
            total = s.filesize
            on_progress(total - remaining, total)

        try:
            yt = self._youtube(video_id, on_progress=callback)
            target = yt.streams.get_by_itag(int(stream.format_id))
            if target is None:
                raise ProviderError("unsupported", f"itag {stream.format_id}")
            target.download(output_path=str(dest.parent), filename=dest.name)
        except DownloadCancelled:
            raise
        except Exception as exc:
            raise map_error(exc) from exc

    def stream_url(self, video_id, stream):
        if not self.is_available():
            raise ProviderError("not_installed", self.name)
        try:
            target = self._youtube(video_id).streams.get_by_itag(int(stream.format_id))
            if target is None:
                raise ProviderError("unsupported", f"itag {stream.format_id}")
            return target.url
        except ProviderError:
            raise
        except Exception as exc:
            raise map_error(exc) from exc
