import os
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from app.domain.errors import DuplicateError, StorageError
from app.domain.models import LOCAL_MISSING, LOCAL_NONE, LOCAL_OK, Video, now_iso
from app.domain.urls import extract_video_id
from app.infrastructure.providers.base import ProviderError
from app.services.storage_service import STATUS_READY
from app.services.thumbnail_service import ThumbnailService, thumbnail_name

SORT_NEWEST = "newest"


class LibraryService(QObject):
    """Regras da biblioteca: salvar, remover, validar o arquivo local e achar miniaturas."""

    changed = Signal()

    def __init__(self, storage, providers, thumbnails=None):
        super().__init__()
        self._storage = storage
        self._providers = providers
        self._thumbs = thumbnails or ThumbnailService()

    # -- acesso -----------------------------------------------------------
    @property
    def ready(self):
        return self._storage.status() == STATUS_READY

    @property
    def store(self):
        return self._storage.store

    @property
    def layout(self):
        return self._storage.layout

    def notify(self):
        self.changed.emit()

    def get(self, video_id):
        return self.store.get_video(video_id) if self.ready else None

    def find(self, source_id, source="youtube"):
        return self.store.find_video(source, source_id) if self.ready else None

    def list_videos(self, newest_first=True):
        if not self.ready:
            return []
        videos = self.store.list_videos()
        videos.sort(key=lambda v: (v.added_at, v.id or 0), reverse=newest_first)
        return videos

    # -- salvar -----------------------------------------------------------
    def fetch_info(self, video_id):
        """Consulta os provedores (rede). Rode fora da thread da interface."""
        return self._providers.fetch_info(video_id)

    def save_info(self, info):
        """Guarda a referência do vídeo (não baixa o arquivo). Devolve (video, created)."""
        existing = self.find(info.source_id, info.source)
        if existing:
            return existing, False
        thumb = self._thumbs.ensure(self.layout, info.source, info.source_id, info.thumbnail_url) or ""
        video = Video(
            source_id=info.source_id,
            url=info.url,
            source=info.source,
            title=info.title,
            channel=info.channel,
            duration=info.duration,
            thumbnail=thumb,
            description=info.description,
        )
        try:
            video = self.store.add_video(video)
        except DuplicateError:  # salvo em paralelo por outra ação
            return self.find(info.source_id, info.source), False
        self.notify()
        return video, True

    def save_url(self, url):
        """Fluxo completo a partir de um link. Levanta ProviderError ou StorageError."""
        video_id = extract_video_id(url)
        if video_id is None:
            raise ProviderError("unsupported", "link inválido")
        existing = self.find(video_id)
        if existing:
            return existing, False
        return self.save_info(self.fetch_info(video_id))

    # -- remover ------------------------------------------------------------
    def remove(self, video_id, delete_file=False):
        """Remove o registro. O arquivo local só é apagado se `delete_file` for pedido, e só dentro da pasta da biblioteca."""
        video = self.get(video_id)
        if video is None:
            return
        if delete_file and video.local_path:
            path = self.local_path(video, must_exist=False)
            if path is not None and path.is_file():
                path.unlink()
        self.store.delete_video(video_id)
        self.notify()

    # -- arquivo local ------------------------------------------------------
    def local_path(self, video, must_exist=True):
        """Caminho absoluto do arquivo local, ou None. Nunca confia só no caminho gravado."""
        if not video.local_path:
            return None
        try:
            path = self.layout.resolve(video.local_path)
        except StorageError:
            return None
        if must_exist and not (path.is_file() and path.stat().st_size > 0):
            return None
        return path

    def validate_local(self, video):
        """Confere o arquivo no disco e corrige o registro se necessário. Devolve o video atualizado."""
        if not video.local_path:
            return video
        path = self.local_path(video)
        status = LOCAL_OK if path is not None else LOCAL_MISSING
        size = path.stat().st_size if path is not None else video.local_size
        if status != video.local_status or size != video.local_size:
            video.local_status, video.local_size, video.validated_at = status, size, now_iso()
            self.store.update_video(video)
        return video

    def validate_all(self):
        changed = False
        for video in self.store.list_videos():
            before = video.local_status
            if self.validate_local(video).local_status != before:
                changed = True
        if changed:
            self.notify()
        return changed

    def attach_local_file(self, video_id, path, quality=None):
        """Registra o arquivo baixado e verificado. Grava o caminho relativo a `videos/` quando possível."""
        video = self.get(video_id)
        if video is None:
            raise StorageError("not_found", f"video {video_id}")
        path = Path(path)
        video.local_path = self.layout.to_stored(path)
        video.local_size = os.path.getsize(path)
        video.local_quality = quality
        video.local_status = LOCAL_OK
        video.validated_at = now_iso()
        self.store.update_video(video)
        self.notify()
        return video

    def clear_local_file(self, video_id):
        video = self.get(video_id)
        if video is not None:
            video.local_path = video.local_size = video.local_quality = video.validated_at = None
            video.local_status = LOCAL_NONE
            self.store.update_video(video)
            self.notify()

    # -- miniaturas -----------------------------------------------------------
    def thumbnail_path(self, video):
        if not video.thumbnail or not self.ready:
            return None
        path = self.layout.thumbnails / thumbnail_name(video.source, video.source_id)
        return path if path.is_file() else None
