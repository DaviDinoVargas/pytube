
from app.infrastructure.providers.base import (
    DownloadCancelled,
    ProviderError,
    StreamOption,
    VideoInfo,
    VideoProvider,
    module_installed,
)

# (trecho da mensagem em minúsculas, código)
_MESSAGES = (
    ("private video", "private"),
    ("confirm your age", "age_restricted"),
    ("age-restricted", "age_restricted"),
    ("members-only", "members_only"),
    ("join this channel", "members_only"),
    ("drm", "drm"),
    ("not a bot", "blocked"),
    ("live event", "live"),
    ("is live", "live"),
    ("urlopen error", "network"),
    ("timed out", "network"),
    ("getaddrinfo", "network"),
    ("unable to download", "network"),
    ("unavailable", "unavailable"),
    ("not available", "unavailable"),
    ("has been removed", "unavailable"),
)


def map_error(exc):
    if isinstance(exc, (DownloadCancelled, ProviderError)):
        return exc
    text = str(exc).lower()
    for needle, code in _MESSAGES:
        if needle in text:
            return ProviderError(code, str(exc)[:300])
    return ProviderError("failed", str(exc)[:300])


def to_option(fmt):
    vcodec = fmt.get("vcodec") or "none"
    acodec = fmt.get("acodec") or "none"
    if vcodec != "none" and acodec != "none":
        kind = "progressive"
    elif vcodec != "none":
        kind = "video"
    elif acodec != "none":
        kind = "audio"
    else:
        return None
    size = fmt.get("filesize") or fmt.get("filesize_approx")
    tbr = fmt.get("abr") if kind == "audio" else fmt.get("tbr")
    return StreamOption(
        kind=kind,
        format_id=str(fmt["format_id"]),
        ext=fmt.get("ext") or "mp4",
        height=fmt.get("height") if kind != "audio" else None,
        fps=int(fmt["fps"]) if fmt.get("fps") and kind != "audio" else None,
        bitrate=int(tbr) if tbr else None,
        filesize=int(size) if size else None,
        vcodec="" if vcodec == "none" else vcodec,
        acodec="" if acodec == "none" else acodec,
    )


class YtdlpProvider(VideoProvider):
    name = "ytdlp"

    def is_available(self):
        return module_installed("yt_dlp")

    @staticmethod
    def _base_options():
        return {"quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": 20}

    def fetch_info(self, video_id):
        if not self.is_available():
            raise ProviderError("not_installed", self.name)
        import yt_dlp

        url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            with yt_dlp.YoutubeDL({**self._base_options(), "skip_download": True}) as ydl:
                data = ydl.extract_info(url, download=False)
        except Exception as exc:
            raise map_error(exc) from exc
        if data.get("is_live"):
            raise ProviderError("live", "transmissão ao vivo")
        streams = [o for o in (to_option(f) for f in data.get("formats", [])) if o is not None]
        return VideoInfo(
            source_id=video_id,
            url=url,
            title=data.get("title") or "",
            channel=data.get("uploader") or data.get("channel") or "",
            duration=int(data["duration"]) if data.get("duration") else None,
            thumbnail_url=data.get("thumbnail") or "",
            description=data.get("description") or "",
            provider=self.name,
            streams=streams,
        )

    def download_stream(self, video_id, stream, dest, on_progress, cancel_event):
        if not self.is_available():
            raise ProviderError("not_installed", self.name)
        import yt_dlp

        def hook(status):
            if cancel_event.is_set():
                raise DownloadCancelled()
            if status.get("status") == "downloading":
                total = status.get("total_bytes") or status.get("total_bytes_estimate") or 0
                on_progress(status.get("downloaded_bytes") or 0, total)

        options = {
            **self._base_options(),
            "format": stream.format_id,
            "outtmpl": str(dest).replace("%", "%%"),
            "progress_hooks": [hook],
            "noprogress": True,
            "overwrites": True,
            "continuedl": True,
        }
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
        except DownloadCancelled:
            raise
        except Exception as exc:
            # yt-dlp embrulha exceções do hook em DownloadError
            if cancel_event.is_set():
                raise DownloadCancelled() from exc
            raise map_error(exc) from exc
