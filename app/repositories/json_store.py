import json
import os
import threading
from pathlib import Path

from app.domain.errors import DuplicateError, NotFoundError, StorageError
from app.domain.models import Category, Playlist, Progress, Video, from_dict, to_dict
from app.repositories.base import SCHEMA_VERSION, LibraryStore, empty_export


class JsonStore(LibraryStore):
    """Biblioteca em um único `library.json` legível, gravado de forma atômica."""

    kind = "json"

    def __init__(self, path):
        self._path = Path(path)
        self._lock = threading.RLock()
        self._data = self._load()

    def _load(self):
        if not self._path.exists():
            data = empty_export()
            self._write(data)
            return data
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # Nunca sobrescreve um arquivo ilegível: o usuário ainda pode recuperá-lo.
            raise StorageError("library_unreadable", str(self._path)) from exc
        if not isinstance(data, dict) or data.get("schema_version", 0) > SCHEMA_VERSION:
            raise StorageError("library_unsupported", str(self._path))
        base = empty_export()
        base.update(data)
        return base

    def _write(self, data):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self._path)

    def _save(self):
        self._write(self._data)

    def _next_id(self, key):
        return max((row["id"] for row in self._data[key]), default=0) + 1

    def _row(self, key, row_id):
        for row in self._data[key]:
            if row["id"] == row_id:
                return row
        return None

    def close(self):
        pass

    # vídeos
    def add_video(self, video):
        with self._lock:
            if self.find_video(video.source, video.source_id):
                raise DuplicateError(f"{video.source}:{video.source_id}")
            video.id = self._next_id("videos")
            self._data["videos"].append(to_dict(video))
            self._save()
            return video

    def get_video(self, video_id):
        with self._lock:
            row = self._row("videos", video_id)
            return from_dict(Video, row) if row else None

    def find_video(self, source, source_id):
        with self._lock:
            for row in self._data["videos"]:
                if row["source"] == source and row["source_id"] == source_id:
                    return from_dict(Video, row)
            return None

    def list_videos(self):
        with self._lock:
            return [from_dict(Video, row) for row in self._data["videos"]]

    def update_video(self, video):
        with self._lock:
            row = self._row("videos", video.id)
            if row is None:
                raise NotFoundError(f"video {video.id}")
            for other in self._data["videos"]:
                if other["id"] != video.id and (other["source"], other["source_id"]) == (video.source, video.source_id):
                    raise DuplicateError(f"{video.source}:{video.source_id}")
            row.update(to_dict(video))
            self._save()

    def delete_video(self, video_id):
        with self._lock:
            self._data["videos"] = [r for r in self._data["videos"] if r["id"] != video_id]
            self._data["video_categories"] = [r for r in self._data["video_categories"] if r[0] != video_id]
            self._data["playlist_items"] = [r for r in self._data["playlist_items"] if r[1] != video_id]
            self._data["progress"] = [r for r in self._data["progress"] if r["video_id"] != video_id]
            self._save()

    # categorias
    def _check_category_name(self, name, own_id=None):
        for row in self._data["categories"]:
            if row["id"] != own_id and row["name"].casefold() == name.casefold():
                raise DuplicateError(name)

    def add_category(self, category):
        with self._lock:
            self._check_category_name(category.name)
            category.id = self._next_id("categories")
            self._data["categories"].append(to_dict(category))
            self._save()
            return category

    def list_categories(self):
        with self._lock:
            return [from_dict(Category, row) for row in self._data["categories"]]

    def update_category(self, category):
        with self._lock:
            row = self._row("categories", category.id)
            if row is None:
                raise NotFoundError(f"category {category.id}")
            self._check_category_name(category.name, category.id)
            row.update(to_dict(category))
            self._save()

    def delete_category(self, category_id):
        with self._lock:
            self._data["categories"] = [r for r in self._data["categories"] if r["id"] != category_id]
            self._data["video_categories"] = [r for r in self._data["video_categories"] if r[1] != category_id]
            self._save()

    def set_video_categories(self, video_id, category_ids):
        with self._lock:
            if self._row("videos", video_id) is None:
                raise NotFoundError(f"video {video_id}")
            ids = list(dict.fromkeys(category_ids))
            for cid in ids:
                if self._row("categories", cid) is None:
                    raise NotFoundError(f"category {cid}")
            self._data["video_categories"] = [r for r in self._data["video_categories"] if r[0] != video_id]
            self._data["video_categories"].extend([video_id, cid] for cid in ids)
            self._save()

    def get_video_category_ids(self, video_id):
        with self._lock:
            return [r[1] for r in self._data["video_categories"] if r[0] == video_id]

    # playlists
    def add_playlist(self, playlist):
        with self._lock:
            playlist.id = self._next_id("playlists")
            self._data["playlists"].append(to_dict(playlist))
            self._save()
            return playlist

    def list_playlists(self):
        with self._lock:
            return [from_dict(Playlist, row) for row in self._data["playlists"]]

    def update_playlist(self, playlist):
        with self._lock:
            row = self._row("playlists", playlist.id)
            if row is None:
                raise NotFoundError(f"playlist {playlist.id}")
            row.update(to_dict(playlist))
            self._save()

    def delete_playlist(self, playlist_id):
        with self._lock:
            self._data["playlists"] = [r for r in self._data["playlists"] if r["id"] != playlist_id]
            self._data["playlist_items"] = [r for r in self._data["playlist_items"] if r[0] != playlist_id]
            self._save()

    def set_playlist_items(self, playlist_id, video_ids):
        with self._lock:
            if self._row("playlists", playlist_id) is None:
                raise NotFoundError(f"playlist {playlist_id}")
            ids = list(dict.fromkeys(video_ids))
            for vid in ids:
                if self._row("videos", vid) is None:
                    raise NotFoundError(f"video {vid}")
            self._data["playlist_items"] = [r for r in self._data["playlist_items"] if r[0] != playlist_id]
            self._data["playlist_items"].extend([playlist_id, vid, pos] for pos, vid in enumerate(ids))
            self._save()

    def get_playlist_items(self, playlist_id):
        with self._lock:
            rows = sorted((r for r in self._data["playlist_items"] if r[0] == playlist_id), key=lambda r: r[2])
            return [r[1] for r in rows]

    # histórico
    def save_progress(self, progress):
        with self._lock:
            if self._row("videos", progress.video_id) is None:
                raise NotFoundError(f"video {progress.video_id}")
            self._data["progress"] = [r for r in self._data["progress"] if r["video_id"] != progress.video_id]
            self._data["progress"].append(to_dict(progress))
            self._save()

    def _row_by_video(self, video_id):
        for row in self._data["progress"]:
            if row["video_id"] == video_id:
                return row
        return None

    def get_progress(self, video_id):
        with self._lock:
            row = self._row_by_video(video_id)
            return from_dict(Progress, row) if row else None

    def delete_progress(self, video_id):
        with self._lock:
            self._data["progress"] = [r for r in self._data["progress"] if r["video_id"] != video_id]
            self._save()

    def clear_history(self):
        with self._lock:
            self._data["progress"] = []
            self._save()

    def list_progress(self):
        with self._lock:
            return [from_dict(Progress, row) for row in self._data["progress"]]

    def list_category_links(self):
        with self._lock:
            return [(r[0], r[1]) for r in self._data["video_categories"]]

    def list_playlist_links(self):
        with self._lock:
            return [(r[0], r[1], r[2]) for r in self._data["playlist_items"]]

    # migração e backup
    def export_data(self):
        with self._lock:
            return json.loads(json.dumps(self._data))

    def import_data(self, data):
        with self._lock:
            if not self.is_empty():
                raise StorageError("target_not_empty", str(self._path))
            if data.get("schema_version", 0) > SCHEMA_VERSION:
                raise StorageError("library_unsupported")
            merged = empty_export()
            merged.update({k: data[k] for k in merged if k in data})
            self._data = merged
            self._save()
