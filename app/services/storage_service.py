import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.domain.errors import StorageError
from app.repositories.json_store import JsonStore
from app.repositories.sqlite_store import SqliteStore

MODE_DATABASE = "database"  # biblioteca em SQLite na pasta de dados do aplicativo
MODE_FOLDER = "folder"  # tudo dentro da pasta escolhida (portátil)
MODES = (MODE_DATABASE, MODE_FOLDER)
FORMAT_JSON = "json"
FORMAT_SQLITE = "sqlite"
FORMATS = (FORMAT_JSON, FORMAT_SQLITE)

# Criadas assim que a pasta é confirmada, para o restante do app nunca precisar criá-las.
SUBFOLDERS = ("videos", "thumbnails", "data", "backups", "logs", "tmp")

STATUS_UNCONFIGURED = "unconfigured"
STATUS_ROOT_MISSING = "root_missing"
STATUS_READY = "ready"


def suggested_root():
    """Sugestão de pasta: A:\\pytube no Windows quando a unidade A: existe; senão ~/DinoTube."""
    if sys.platform == "win32" and os.path.isdir("A:\\"):
        return Path("A:\\pytube")
    return Path.home() / "DinoTube"


def validate_root(path):
    """Normaliza e valida a pasta raiz. Cria-a se não existir. Levanta StorageError com um código estável."""
    text = str(path or "").strip()
    if not text or "\0" in text:
        raise StorageError("path_empty")
    root = Path(text).expanduser()
    if not root.is_absolute():
        raise StorageError("path_not_absolute", text)
    if root.exists() and not root.is_dir():
        raise StorageError("path_not_directory", str(root))
    try:
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=root, prefix=".dinotube-write-test-"):
            pass
    except OSError as exc:
        raise StorageError("path_not_writable", f"{root}: {exc.strerror or exc}") from exc
    return root


class StorageLayout:
    """Subpastas da biblioteca dentro da raiz escolhida pelo usuário."""

    def __init__(self, root):
        self.root = Path(root)

    def __getattr__(self, name):
        if name in SUBFOLDERS:
            return self.root / name
        raise AttributeError(name)

    def create(self):
        for name in SUBFOLDERS:
            (self.root / name).mkdir(parents=True, exist_ok=True)

    def missing(self):
        return [name for name in SUBFOLDERS if not (self.root / name).is_dir()]

    def to_stored(self, path):
        """Caminho a gravar no registro: relativo a `videos/` quando possível, para a pasta ser movível."""
        path = Path(path)
        try:
            return path.resolve().relative_to(self.videos.resolve()).as_posix()
        except ValueError:
            return str(path)

    def resolve(self, stored):
        """Caminho absoluto de um registro. Recusa caminhos relativos que escapam de `videos/`."""
        path = Path(stored)
        if path.is_absolute():
            return path
        full = (self.videos / path).resolve()
        if not full.is_relative_to(self.videos.resolve()):
            raise StorageError("path_escapes_root", stored)
        return full


@dataclass(frozen=True)
class StorageConfig:
    root: Path
    mode: str = MODE_FOLDER
    format: str = FORMAT_SQLITE

    def __post_init__(self):
        if self.mode not in MODES or self.format not in FORMATS:
            raise StorageError("config_invalid", f"{self.mode}/{self.format}")


@dataclass(frozen=True)
class MigrationPlan:
    videos: int
    categories: int
    playlists: int
    target_has_data: bool
    same_location: bool


class StorageManager:
    """Escolhe, cria e troca onde a biblioteca mora. Não move arquivos de vídeo, só registros."""

    def __init__(self, settings, app_data_dir):
        self._settings = settings
        self._app_data = Path(app_data_dir)
        self._store = None
        self.config = self._read_config()

    # -- configuração ---------------------------------------------------
    def _read_config(self):
        root = self._settings.storage_root
        if not root:
            return None
        try:
            return StorageConfig(Path(root), self._settings.storage_mode, self._settings.storage_format)
        except StorageError:
            return None

    def status(self):
        if self.config is None:
            return STATUS_UNCONFIGURED
        if not self.config.root.is_dir():
            return STATUS_ROOT_MISSING
        return STATUS_READY

    @property
    def layout(self):
        return StorageLayout(self.config.root) if self.config else None

    def _store_path(self, config):
        if config.mode == MODE_DATABASE:
            return self._app_data / "library.db"
        suffix = "json" if config.format == FORMAT_JSON else "db"
        return config.root / "data" / f"library.{suffix}"

    @staticmethod
    def _effective(config):
        # No modo banco o formato é sempre SQLite
        return StorageConfig(config.root, config.mode, FORMAT_SQLITE) if config.mode == MODE_DATABASE else config

    def _open(self, config):
        config = self._effective(config)
        path = self._store_path(config)
        return JsonStore(path) if config.format == FORMAT_JSON else SqliteStore(path)

    @property
    def store(self):
        if self.status() != STATUS_READY:
            raise StorageError("storage_not_ready", self.status())
        if self._store is None:
            self.layout.create()
            self._store = self._open(self.config)
        return self._store

    # -- troca de local --------------------------------------------------
    def plan(self, root, mode, fmt):
        """Prévia da troca: quantos registros seriam copiados e se o destino já tem dados."""
        target = self._effective(StorageConfig(Path(root), mode, fmt))
        current_counts = {"videos": 0, "categories": 0, "playlists": 0}
        same = False
        if self.status() == STATUS_READY:
            current_counts = self.store.counts()
            same = self._store_path(self._effective(self.config)) == self._store_path(target)
        has_data = False
        path = self._store_path(target)
        if path.exists() and not same:
            probe = self._open(target)
            try:
                has_data = not probe.is_empty()
            finally:
                probe.close()
        return MigrationPlan(
            videos=current_counts["videos"],
            categories=current_counts["categories"],
            playlists=current_counts["playlists"],
            target_has_data=has_data,
            same_location=same,
        )

    def configure(self, root, mode, fmt, migrate=False):
        """Valida a pasta, cria as subpastas e passa a usar o novo local.

        Com `migrate=True`, copia os registros da biblioteca atual para o destino, confere o resultado
        e só então troca. A biblioteca antiga nunca é apagada nem alterada.
        """
        root = validate_root(root)
        new = StorageConfig(root, mode, fmt)
        StorageLayout(root).create()
        effective = self._effective(new)
        source = self.store if (migrate and self.status() == STATUS_READY) else None
        same = (
            self.status() == STATUS_READY
            and self._store_path(self._effective(self.config)) == self._store_path(effective)
        )
        target = self.store if same else self._open(effective)
        try:
            if source is not None and not same:
                if not target.is_empty():
                    raise StorageError("target_not_empty", str(self._store_path(effective)))
                data = source.export_data()
                target.import_data(data)
                if target.export_data() != data:
                    raise StorageError("migration_verification_failed")
        except Exception:
            if not same:
                target.close()
            raise
        previous = self._store
        self._settings.storage_root = str(root)
        self._settings.storage_mode = mode
        self._settings.storage_format = fmt
        self.config = new
        self._store = target
        if previous is not None and previous is not target:
            previous.close()
        return target

    # -- uso de espaço ---------------------------------------------------
    def usage(self):
        """Espaço livre do disco e o que a pasta de vídeos ocupa."""
        layout = self.layout
        total, _used, free = shutil.disk_usage(layout.root)
        size = count = 0
        for base, _dirs, files in os.walk(layout.videos):
            for name in files:
                try:
                    size += os.path.getsize(os.path.join(base, name))
                    count += 1
                except OSError:
                    pass
        return {"free": free, "total": total, "videos_bytes": size, "video_files": count}

    def close(self):
        if self._store is not None:
            self._store.close()
            self._store = None


def format_bytes(value):
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
