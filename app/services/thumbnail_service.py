import re
import urllib.request
from urllib.parse import urlparse

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QImage

_ALLOWED_HOSTS = ("ytimg.com", "ggpht.com", "googleusercontent.com", "youtube.com")
_MAX_BYTES = 3 * 1024 * 1024
MAX_WIDTH = 480


def _http_get(url):
    request = urllib.request.Request(url, headers={"User-Agent": "DinoTube"})
    with urllib.request.urlopen(request, timeout=10) as response:
        data = response.read(_MAX_BYTES + 1)
    if len(data) > _MAX_BYTES:
        raise ValueError("miniatura grande demais")
    return data


def is_allowed_url(url):
    """Metadados remotos não são confiáveis: só HTTPS e só hosts de imagem conhecidos."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(host == h or host.endswith("." + h) for h in _ALLOWED_HOSTS)


def thumbnail_name(source, source_id):
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", f"{source}_{source_id}")
    return f"{safe}.jpg"


class ThumbnailService:
    def __init__(self, fetch=_http_get):
        self._fetch = fetch

    def ensure(self, layout, source, source_id, url):
        """Baixa e guarda a miniatura. Devolve o nome do arquivo, ou None se não foi possível."""
        name = thumbnail_name(source, source_id)
        target = layout.thumbnails / name
        if target.is_file() and target.stat().st_size > 0:
            return name
        if not url or not is_allowed_url(url):
            return None
        try:
            image = QImage.fromData(QByteArray(self._fetch(url)))
        except Exception:
            return None
        if image.isNull():
            return None
        if image.width() > MAX_WIDTH:
            image = image.scaledToWidth(MAX_WIDTH, Qt.SmoothTransformation)
        layout.thumbnails.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".jpg.tmp")
        if not image.save(str(tmp), "JPG", 85):
            return None
        tmp.replace(target)
        return name
