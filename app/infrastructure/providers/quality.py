"""Escolha de qualidade, independente do provedor."""

from dataclasses import dataclass

from app.infrastructure.providers.base import ProviderError, StreamOption

_MP4_VIDEO = ("avc1", "h264")
_MP4_AUDIO = ("mp4a", "aac")


@dataclass(frozen=True)
class Selection:
    height: int
    video: StreamOption
    audio: StreamOption | None = None  # None: stream progressivo (já tem áudio)

    @property
    def mode(self):
        return "direct" if self.audio is None else "merge"

    @property
    def label(self):
        return self.video.label


def _starts(codec, prefixes):
    return (codec or "").lower().startswith(prefixes)


def _video_score(s):
    # prefere MP4/H.264 (junta sem recodificar), depois mais quadros e mais bitrate
    return (
        1 if s.ext == "mp4" else 0,
        1 if _starts(s.vcodec, _MP4_VIDEO) else 0,
        s.fps or 0,
        s.bitrate or 0,
    )


def _audio_score(s):
    return (
        1 if s.ext in ("mp4", "m4a") else 0,
        1 if _starts(s.acodec, _MP4_AUDIO) else 0,
        s.bitrate or 0,
    )


def best_audio(streams):
    audios = [s for s in streams if s.kind == "audio"]
    return max(audios, key=_audio_score) if audios else None


def available_heights(streams):
    """Alturas que o app consegue entregar com som, da maior para a menor."""
    has_audio = best_audio(streams) is not None
    heights = set()
    for s in streams:
        if not s.height:
            continue
        if s.kind == "progressive" or (s.kind == "video" and has_audio):
            heights.add(s.height)
    return sorted(heights, reverse=True)


def pick(streams, height, prefer_progressive=True):
    """Seleciona o que baixar para `height`. Levanta ProviderError('unsupported') se não houver como."""
    progressive = [s for s in streams if s.kind == "progressive" and s.height == height]
    video_only = [s for s in streams if s.kind == "video" and s.height == height]
    audio = best_audio(streams)
    if progressive and (prefer_progressive or not (video_only and audio)):
        return Selection(height, max(progressive, key=_video_score))
    if video_only and audio:
        return Selection(height, max(video_only, key=_video_score), audio)
    if progressive:
        return Selection(height, max(progressive, key=_video_score))
    raise ProviderError("unsupported", f"{height}p")


def default_height(streams, player_height=None):
    """Altura padrão do download: a que está no player, ou a mais próxima abaixo dela, ou a maior."""
    heights = available_heights(streams)
    if not heights:
        return None
    if player_height:
        not_above = [h for h in heights if h <= player_height]
        return not_above[0] if not_above else heights[-1]
    return heights[0]


def equivalent(stream, candidates):
    """Stream equivalente de outro provedor, para o fallback no meio de um download."""
    same = [c for c in candidates if c.kind == stream.kind and c.height == stream.height]
    if not same:
        return None
    return max(same, key=_audio_score if stream.kind == "audio" else _video_score)


def needs_recode(selection):
    """True quando juntar em MP4 sem recodificar não é seguro (ex.: VP9/AV1 + Opus)."""
    v_ok = _starts(selection.video.vcodec, _MP4_VIDEO) or not selection.video.vcodec and selection.video.ext == "mp4"
    if selection.audio is None:
        return not v_ok
    a_ok = _starts(selection.audio.acodec, _MP4_AUDIO) or not selection.audio.acodec and selection.audio.ext in ("mp4", "m4a")
    return not (v_ok and a_ok)


def recode_plan(selection):
    """(copiar_video, copiar_audio): copia o que já é compatível com MP4 e recodifica só o resto."""
    video = selection.video
    copy_video = _starts(video.vcodec, _MP4_VIDEO) or (not video.vcodec and video.ext == "mp4")
    audio = selection.audio
    if audio is None:
        return copy_video, True
    copy_audio = _starts(audio.acodec, _MP4_AUDIO) or (not audio.acodec and audio.ext in ("mp4", "m4a"))
    return copy_video, copy_audio
