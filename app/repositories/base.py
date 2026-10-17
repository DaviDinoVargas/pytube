from abc import ABC, abstractmethod

SCHEMA_VERSION = 2  # v2: Video.notes
EXPORT_KEYS = ("videos", "categories", "playlists", "video_categories", "playlist_items", "progress")


def empty_export():
    data = {key: [] for key in EXPORT_KEYS}
    data["schema_version"] = SCHEMA_VERSION
    return data


def normalize_export(data):
    """Completa cada linha com os valores padrão do modelo (backups antigos podem não ter campos novos).

    Levanta StorageError('library_import_invalid') se faltar algo obrigatório (ex.: source_id)."""
    from app.domain.errors import StorageError
    from app.domain.models import Category, Playlist, Progress, Video, from_dict, to_dict

    out = empty_export()
    out["schema_version"] = data.get("schema_version", SCHEMA_VERSION)
    try:
        for key, model in (("videos", Video), ("categories", Category), ("playlists", Playlist), ("progress", Progress)):
            out[key] = [to_dict(from_dict(model, row)) for row in data.get(key, [])]
    except (TypeError, AttributeError) as exc:
        raise StorageError("library_import_invalid", str(exc)) from exc
    for key in ("video_categories", "playlist_items"):
        out[key] = [list(link) for link in data.get(key, [])]
    return out


class LibraryStore(ABC):
    """Contrato único da biblioteca. SQLite e JSON implementam exatamente o mesmo comportamento."""

    kind = ""

    @abstractmethod
    def close(self): ...

    # vídeos
    @abstractmethod
    def add_video(self, video): ...

    @abstractmethod
    def get_video(self, video_id): ...

    @abstractmethod
    def find_video(self, source, source_id): ...

    @abstractmethod
    def list_videos(self): ...

    @abstractmethod
    def update_video(self, video): ...

    @abstractmethod
    def delete_video(self, video_id): ...

    # categorias
    @abstractmethod
    def add_category(self, category): ...

    @abstractmethod
    def list_categories(self): ...

    @abstractmethod
    def update_category(self, category): ...

    @abstractmethod
    def delete_category(self, category_id): ...

    @abstractmethod
    def set_video_categories(self, video_id, category_ids): ...

    @abstractmethod
    def get_video_category_ids(self, video_id): ...

    # playlists
    @abstractmethod
    def add_playlist(self, playlist): ...

    @abstractmethod
    def list_playlists(self): ...

    @abstractmethod
    def update_playlist(self, playlist): ...

    @abstractmethod
    def delete_playlist(self, playlist_id): ...

    @abstractmethod
    def set_playlist_items(self, playlist_id, video_ids): ...

    @abstractmethod
    def get_playlist_items(self, playlist_id): ...

    # histórico
    @abstractmethod
    def save_progress(self, progress): ...

    @abstractmethod
    def get_progress(self, video_id): ...

    @abstractmethod
    def clear_history(self): ...

    @abstractmethod
    def delete_progress(self, video_id): ...

    @abstractmethod
    def list_progress(self): ...

    # vínculos em lote (a busca carrega tudo de uma vez, sem consultar vídeo por vídeo)
    @abstractmethod
    def list_category_links(self): ...

    @abstractmethod
    def list_playlist_links(self): ...

    # migração e backup
    @abstractmethod
    def export_data(self): ...

    @abstractmethod
    def import_data(self, data): ...

    @abstractmethod
    def replace_data(self, data):
        """Troca TODO o conteúdo pelo de `data`, de forma atômica: se falhar, o conteúdo antigo continua intacto."""

    def is_empty(self):
        return not any(self.export_data()[key] for key in EXPORT_KEYS)

    def counts(self):
        data = self.export_data()
        return {key: len(data[key]) for key in ("videos", "categories", "playlists")}
