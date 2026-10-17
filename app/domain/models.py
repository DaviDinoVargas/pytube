from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone

# Estado do arquivo local de um vídeo. "salvo" é o padrão: só existe a referência.
LOCAL_NONE = "none"
LOCAL_OK = "ok"
LOCAL_MISSING = "missing"
LOCAL_INVALID = "invalid"


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Video:
    """Registro do vídeo. O arquivo local e a fonte online são campos distintos."""

    source_id: str
    url: str
    source: str = "youtube"
    title: str = ""
    channel: str = ""
    duration: int | None = None
    thumbnail: str = ""
    description: str = ""
    added_at: str = field(default_factory=now_iso)
    local_path: str | None = None
    local_size: int | None = None
    local_quality: str | None = None
    local_status: str = LOCAL_NONE
    validated_at: str | None = None
    notes: str = ""  # anotações do usuário sobre o vídeo
    id: int | None = None


@dataclass
class Category:
    name: str
    description: str = ""
    color: str | None = None
    created_at: str = field(default_factory=now_iso)
    id: int | None = None


@dataclass
class Playlist:
    name: str
    description: str = ""
    created_at: str = field(default_factory=now_iso)
    id: int | None = None


@dataclass
class Progress:
    video_id: int
    position: float = 0.0
    duration: float | None = None
    watched: bool = False
    last_played_at: str = field(default_factory=now_iso)


def to_dict(obj):
    return asdict(obj)


def from_dict(cls, data):
    """Cria o modelo ignorando chaves desconhecidas, para aceitar dados de versões futuras."""
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in names})
