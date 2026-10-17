import importlib.util
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

# Códigos de erro estáveis, traduzidos pela interface (error.provider_<codigo>)
ERROR_CODES = (
    "unavailable", "private", "age_restricted", "members_only", "live", "drm",
    "blocked", "network", "unsupported", "not_installed", "failed",
)
# Erros que nenhum outro provedor resolve: não adianta tentar de novo
TERMINAL_CODES = frozenset({"private", "age_restricted", "members_only", "drm"})


def module_installed(name):
    """True se o módulo já está carregado ou pode ser importado. Nunca levanta exceção."""
    if name in sys.modules:
        return sys.modules[name] is not None
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


class ProviderError(Exception):
    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


class DownloadCancelled(Exception):
    """Levantada dentro do callback de progresso para interromper um download."""


@dataclass(frozen=True)
class StreamOption:
    """Um stream disponível. `kind` é 'progressive' (vídeo+áudio), 'video' (só vídeo) ou 'audio'."""

    kind: str
    format_id: str
    ext: str = "mp4"
    height: int | None = None
    fps: int | None = None
    bitrate: int | None = None  # kbps
    filesize: int | None = None
    vcodec: str = ""
    acodec: str = ""

    @property
    def label(self):
        if not self.height:
            return ""
        return f"{self.height}p{self.fps}" if self.fps and self.fps > 30 else f"{self.height}p"


@dataclass
class VideoInfo:
    source_id: str
    url: str
    title: str = ""
    channel: str = ""
    duration: int | None = None
    thumbnail_url: str = ""
    description: str = ""
    source: str = "youtube"
    provider: str = ""
    streams: list = field(default_factory=list)


class VideoProvider(ABC):
    name = ""

    @abstractmethod
    def is_available(self): ...

    @abstractmethod
    def fetch_info(self, video_id): ...

    @abstractmethod
    def download_stream(self, video_id, stream, dest, on_progress, cancel_event):
        """Baixa `stream` para o caminho exato `dest`. `on_progress(feito, total)`; `cancel_event` é um threading.Event."""
