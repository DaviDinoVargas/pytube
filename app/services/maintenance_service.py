import os
from dataclasses import dataclass
from pathlib import Path

from app.domain.errors import StorageError
from app.domain.models import LOCAL_INVALID, LOCAL_MISSING, LOCAL_OK
from app.infrastructure.media.ffmpeg import MediaError
from app.infrastructure.providers.base import ProviderError

VIDEO_SUFFIXES = frozenset({".mp4", ".mkv", ".webm", ".m4v", ".mov", ".avi"})


@dataclass(frozen=True)
class FileEntry:
    video: object
    path: Path
    size: int


@dataclass(frozen=True)
class Orphan:
    path: Path
    size: int


@dataclass(frozen=True)
class RefreshResult:
    updated: int
    failed: tuple  # ((video_id, código), ...)


class MaintenanceService:
    """Espaço, arquivos ausentes ou soltos, e atualização de metadados da biblioteca."""

    def __init__(self, library, storage, thumbnails=None):
        self._library = library
        self._storage = storage
        self._thumbs = thumbnails

    # -- verificar e resumir -----------------------------------------------------------------
    def verify_all(self):
        """Confere no disco todos os arquivos registrados. Devolve contagens por estado."""
        self._library.validate_all()
        counts = {"downloaded": 0, "missing": 0, "invalid": 0, "saved": 0}
        for video in self._library.store.list_videos():
            key = {LOCAL_OK: "downloaded", LOCAL_MISSING: "missing", LOCAL_INVALID: "invalid"}.get(video.local_status, "saved")
            counts[key] += 1
        return counts

    def summary(self):
        usage = self._storage.usage()
        counts = self._library.store.counts()
        return {
            "free": usage["free"], "total": usage["total"], "videos_bytes": usage["videos_bytes"], "video_files": usage["video_files"],
            "videos": counts["videos"], "categories": counts["categories"], "playlists": counts["playlists"],
        }

    def largest(self, limit=20):
        """Arquivos baixados do maior para o menor (tamanho real no disco). Base da limpeza de espaço."""
        entries = []
        for video in self._library.store.list_videos():
            path = self._library.local_path(video)
            if path is not None:
                entries.append(FileEntry(video, path, path.stat().st_size))
        entries.sort(key=lambda e: e.size, reverse=True)
        return entries[:limit]

    def problems(self):
        """Vídeos cujo arquivo sumiu ou é inválido (o registro continua na biblioteca)."""
        return [v for v in self._library.store.list_videos() if v.local_status in (LOCAL_MISSING, LOCAL_INVALID)]

    # -- espaço --------------------------------------------------------------------------------
    def free_space_of(self, video_ids):
        """Aplica 'apagar só o arquivo' em vários vídeos. Devolve os bytes liberados."""
        total = 0
        for video_id in video_ids:
            total += self._library.delete_local_file(video_id, notify=False)
        self._library.notify()
        return total

    # -- localizar de novo --------------------------------------------------------------------
    def relocate(self, video_id, path, tools):
        """Liga um arquivo existente a um vídeo cujo arquivo sumiu. O arquivo precisa ser mídia válida (com imagem e som)."""
        path = Path(path)
        video = self._library.get(video_id)
        if video is None:
            raise StorageError("not_found", f"video {video_id}")
        if not path.is_file() or path.suffix.lower() not in VIDEO_SUFFIXES:
            raise StorageError("relocate_invalid", "não é um arquivo de vídeo")
        resolved = path.resolve()
        for other in self._library.store.list_videos():
            if other.id != video_id and (self._library.local_path(other) or Path()).resolve() == resolved:
                raise StorageError("relocate_in_use", f"usado por {other.id}")
        info = tools.probe(path)  # MediaError('invalid_media') se não for mídia legível
        if not info.has_video or not info.has_audio or info.duration <= 0:
            raise MediaError("invalid_media", "sem vídeo, sem áudio ou sem duração")
        return self._library.attach_local_file(video_id, path, video.local_quality)

    # -- arquivos soltos -----------------------------------------------------------------------
    def find_orphans(self):
        """Arquivos de vídeo dentro de `videos/` que nenhum registro usa."""
        referenced = set()
        for video in self._library.store.list_videos():
            path = self._library.local_path(video, must_exist=False)
            if path is not None:
                referenced.add(path.resolve())
        orphans = []
        root = self._library.layout.videos
        for base, _dirs, files in os.walk(root):
            for name in files:
                path = Path(base) / name
                if path.suffix.lower() in VIDEO_SUFFIXES and path.resolve() not in referenced:
                    try:
                        orphans.append(Orphan(path, path.stat().st_size))
                    except OSError:
                        pass
        return sorted(orphans, key=lambda o: o.size, reverse=True)

    def delete_orphan(self, path):
        """Apaga um arquivo solto. Recusa qualquer caminho fora de `videos/` ou que algum registro ainda use."""
        path = Path(path)
        if not self._library.is_inside_library(path):
            raise StorageError("path_escapes_root", str(path))
        if path.resolve() not in {o.path.resolve() for o in self.find_orphans()}:
            raise StorageError("not_orphan", str(path))
        size = path.stat().st_size
        path.unlink()
        return size

    # -- miniaturas e metadados -----------------------------------------------------------------
    def clear_thumbnail_cache(self):
        """Apaga as miniaturas guardadas. Devolve (arquivos, bytes). Voltam ao atualizar os metadados."""
        folder = self._library.layout.thumbnails
        count = size = 0
        if folder.is_dir():
            for entry in folder.iterdir():
                if entry.is_file():
                    size += entry.stat().st_size
                    entry.unlink()
                    count += 1
        self._library.notify()
        return count, size

    def refresh_metadata(self, video_ids=None, progress=None):
        """Consulta de novo título, canal, duração, descrição e miniatura. Falhas em um vídeo não param os outros."""
        videos = [v for v in self._library.store.list_videos() if video_ids is None or v.id in set(video_ids)]
        updated, failed = 0, []
        for index, video in enumerate(videos):
            if progress:
                progress(index, len(videos))
            try:
                info = self._library.fetch_info(video.source_id)
            except ProviderError as exc:
                failed.append((video.id, exc.code))
                continue
            video.title, video.channel = info.title or video.title, info.channel or video.channel
            video.duration, video.description = info.duration or video.duration, info.description or video.description
            thumb = self._thumbs.ensure(self._library.layout, video.source, video.source_id, info.thumbnail_url) if self._thumbs else None
            if thumb:
                video.thumbnail = thumb
            self._library.store.update_video(video)
            updated += 1
        if progress:
            progress(len(videos), len(videos))
        self._library.notify()
        return RefreshResult(updated, tuple(failed))
