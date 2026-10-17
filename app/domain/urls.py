import re
from urllib.parse import parse_qs, urlparse

_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}


def extract_video_id(text):
    """Devolve o id de 11 caracteres de um link do YouTube, ou None se o link não for reconhecido."""
    text = (text or "").strip()
    if not text:
        return None
    if "://" not in text:
        text = "https://" + text
    try:
        url = urlparse(text)
    except ValueError:
        return None
    if url.scheme not in ("http", "https"):
        return None
    host = (url.hostname or "").lower()
    candidate = None
    if host == "youtu.be":
        candidate = url.path.lstrip("/").split("/")[0]
    elif host in _HOSTS:
        if url.path == "/watch":
            candidate = parse_qs(url.query).get("v", [None])[0]
        else:
            parts = [p for p in url.path.split("/") if p]
            if len(parts) >= 2 and parts[0] in ("shorts", "embed", "live", "v"):
                candidate = parts[1]
    if candidate and _ID.match(candidate):
        return candidate
    return None
