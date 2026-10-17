from app.domain.models import LOCAL_INVALID, LOCAL_MISSING, LOCAL_OK

# Estado exibido de um vídeo. "saved" = só a referência está guardada; "downloaded" = arquivo local verificado.
SAVED = "saved"
DOWNLOADED = "downloaded"
MISSING = "missing"
INVALID = "invalid"
DOWNLOADING = "downloading"
FAILED = "failed"


def video_state(video, download_status=None):
    """Estado a mostrar. Um download ativo ou com falha tem prioridade sobre o estado do arquivo."""
    if download_status in (DOWNLOADING, FAILED):
        return download_status
    if video.local_status == LOCAL_OK:
        return DOWNLOADED
    if video.local_status == LOCAL_MISSING:
        return MISSING
    if video.local_status == LOCAL_INVALID:
        return INVALID
    return SAVED


def format_duration(seconds):
    if not seconds or seconds < 0:
        return ""
    seconds = int(seconds)
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
