import shutil
import sqlite3
import threading
from dataclasses import fields
from pathlib import Path

from app.domain.errors import DuplicateError, NotFoundError, StorageError
from app.domain.models import Category, Playlist, Progress, Video, from_dict
from app.repositories.base import SCHEMA_VERSION, LibraryStore, empty_export, normalize_export

# Cada item é a migração da versão N para N+1. user_version guarda a versão aplicada.
MIGRATIONS = [
    """
    CREATE TABLE videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        source_id TEXT NOT NULL,
        url TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        channel TEXT NOT NULL DEFAULT '',
        duration INTEGER,
        thumbnail TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        added_at TEXT NOT NULL,
        local_path TEXT,
        local_size INTEGER,
        local_quality TEXT,
        local_status TEXT NOT NULL DEFAULT 'none',
        validated_at TEXT,
        UNIQUE (source, source_id)
    );
    CREATE TABLE categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE COLLATE NOCASE,
        description TEXT NOT NULL DEFAULT '',
        color TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE playlists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    );
    CREATE TABLE video_categories (
        video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
        category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
        PRIMARY KEY (video_id, category_id)
    );
    CREATE TABLE playlist_items (
        playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
        video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
        position INTEGER NOT NULL,
        PRIMARY KEY (playlist_id, video_id)
    );
    CREATE TABLE progress (
        video_id INTEGER PRIMARY KEY REFERENCES videos(id) ON DELETE CASCADE,
        position REAL NOT NULL DEFAULT 0,
        duration REAL,
        watched INTEGER NOT NULL DEFAULT 0,
        last_played_at TEXT NOT NULL
    );
    CREATE INDEX idx_videos_title ON videos(title);
    CREATE INDEX idx_videos_added ON videos(added_at);
    CREATE INDEX idx_videos_status ON videos(local_status);
    """,
]

_VIDEO_COLS = [f.name for f in fields(Video) if f.name != "id"]
_CATEGORY_COLS = [f.name for f in fields(Category) if f.name != "id"]
_PLAYLIST_COLS = [f.name for f in fields(Playlist) if f.name != "id"]
_PROGRESS_COLS = [f.name for f in fields(Progress)]


def _insert(table, cols):
    # Os nomes de coluna vêm dos modelos, nunca de entrada externa; os valores são sempre parametrizados.
    return f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"


def _update(table, cols):
    return f"UPDATE {table} SET {', '.join(c + ' = ?' for c in cols)} WHERE id = ?"


class SqliteStore(LibraryStore):
    kind = "sqlite"

    def __init__(self, path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        try:
            self._db = sqlite3.connect(str(self._path), check_same_thread=False)
            self._db.row_factory = sqlite3.Row
            self._db.execute("PRAGMA foreign_keys = ON")
            self._migrate()
        except sqlite3.DatabaseError as exc:
            raise StorageError("library_unreadable", str(self._path)) from exc

    def _migrate(self):
        current = self._db.execute("PRAGMA user_version").fetchone()[0]
        if current > len(MIGRATIONS):
            raise StorageError("library_unsupported", str(self._path))
        if current == len(MIGRATIONS):
            return
        if current > 0:  # cópia de segurança antes de alterar um banco já existente
            shutil.copy2(self._path, self._path.with_name(f"{self._path.name}.bak-v{current}"))
        for version in range(current, len(MIGRATIONS)):
            with self._db:
                for statement in MIGRATIONS[version].split(";"):
                    if statement.strip():
                        self._db.execute(statement)
                self._db.execute(f"PRAGMA user_version = {version + 1}")

    def close(self):
        with self._lock:
            self._db.close()

    def _one(self, sql, params=()):
        with self._lock:
            return self._db.execute(sql, params).fetchone()

    def _all(self, sql, params=()):
        with self._lock:
            return self._db.execute(sql, params).fetchall()

    # vídeos
    def add_video(self, video):
        with self._lock:
            try:
                with self._db:
                    cur = self._db.execute(_insert("videos", _VIDEO_COLS), [getattr(video, c) for c in _VIDEO_COLS])
            except sqlite3.IntegrityError as exc:
                raise DuplicateError(f"{video.source}:{video.source_id}") from exc
            video.id = cur.lastrowid
            return video

    def get_video(self, video_id):
        row = self._one("SELECT * FROM videos WHERE id = ?", (video_id,))
        return from_dict(Video, dict(row)) if row else None

    def find_video(self, source, source_id):
        row = self._one("SELECT * FROM videos WHERE source = ? AND source_id = ?", (source, source_id))
        return from_dict(Video, dict(row)) if row else None

    def list_videos(self):
        return [from_dict(Video, dict(r)) for r in self._all("SELECT * FROM videos ORDER BY id")]

    def update_video(self, video):
        with self._lock:
            try:
                with self._db:
                    cur = self._db.execute(
                        _update("videos", _VIDEO_COLS), [getattr(video, c) for c in _VIDEO_COLS] + [video.id]
                    )
            except sqlite3.IntegrityError as exc:
                raise DuplicateError(f"{video.source}:{video.source_id}") from exc
            if cur.rowcount == 0:
                raise NotFoundError(f"video {video.id}")

    def delete_video(self, video_id):
        with self._lock, self._db:
            self._db.execute("DELETE FROM videos WHERE id = ?", (video_id,))

    # categorias
    def add_category(self, category):
        with self._lock:
            try:
                with self._db:
                    cur = self._db.execute(
                        _insert("categories", _CATEGORY_COLS), [getattr(category, c) for c in _CATEGORY_COLS]
                    )
            except sqlite3.IntegrityError as exc:
                raise DuplicateError(category.name) from exc
            category.id = cur.lastrowid
            return category

    def list_categories(self):
        return [from_dict(Category, dict(r)) for r in self._all("SELECT * FROM categories ORDER BY id")]

    def update_category(self, category):
        with self._lock:
            try:
                with self._db:
                    cur = self._db.execute(
                        _update("categories", _CATEGORY_COLS), [getattr(category, c) for c in _CATEGORY_COLS] + [category.id]
                    )
            except sqlite3.IntegrityError as exc:
                raise DuplicateError(category.name) from exc
            if cur.rowcount == 0:
                raise NotFoundError(f"category {category.id}")

    def delete_category(self, category_id):
        with self._lock, self._db:
            self._db.execute("DELETE FROM categories WHERE id = ?", (category_id,))

    def set_video_categories(self, video_id, category_ids):
        ids = list(dict.fromkeys(category_ids))
        with self._lock:
            try:
                with self._db:
                    self._db.execute("DELETE FROM video_categories WHERE video_id = ?", (video_id,))
                    self._db.executemany(
                        "INSERT INTO video_categories (video_id, category_id) VALUES (?, ?)", [(video_id, c) for c in ids]
                    )
            except sqlite3.IntegrityError as exc:
                raise NotFoundError(f"video {video_id} ou categorias {ids}") from exc

    def get_video_category_ids(self, video_id):
        rows = self._all("SELECT category_id FROM video_categories WHERE video_id = ? ORDER BY rowid", (video_id,))
        return [r[0] for r in rows]

    # playlists
    def add_playlist(self, playlist):
        with self._lock, self._db:
            cur = self._db.execute(_insert("playlists", _PLAYLIST_COLS), [getattr(playlist, c) for c in _PLAYLIST_COLS])
            playlist.id = cur.lastrowid
            return playlist

    def list_playlists(self):
        return [from_dict(Playlist, dict(r)) for r in self._all("SELECT * FROM playlists ORDER BY id")]

    def update_playlist(self, playlist):
        with self._lock, self._db:
            cur = self._db.execute(
                _update("playlists", _PLAYLIST_COLS), [getattr(playlist, c) for c in _PLAYLIST_COLS] + [playlist.id]
            )
            if cur.rowcount == 0:
                raise NotFoundError(f"playlist {playlist.id}")

    def delete_playlist(self, playlist_id):
        with self._lock, self._db:
            self._db.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))

    def set_playlist_items(self, playlist_id, video_ids):
        ids = list(dict.fromkeys(video_ids))
        with self._lock:
            try:
                with self._db:
                    self._db.execute("DELETE FROM playlist_items WHERE playlist_id = ?", (playlist_id,))
                    self._db.executemany(
                        "INSERT INTO playlist_items (playlist_id, video_id, position) VALUES (?, ?, ?)",
                        [(playlist_id, vid, pos) for pos, vid in enumerate(ids)],
                    )
            except sqlite3.IntegrityError as exc:
                raise NotFoundError(f"playlist {playlist_id} ou vídeos {ids}") from exc

    def get_playlist_items(self, playlist_id):
        rows = self._all("SELECT video_id FROM playlist_items WHERE playlist_id = ? ORDER BY position", (playlist_id,))
        return [r[0] for r in rows]

    # histórico
    def save_progress(self, progress):
        with self._lock:
            try:
                with self._db:
                    self._db.execute(
                        "INSERT OR REPLACE INTO progress (video_id, position, duration, watched, last_played_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (progress.video_id, progress.position, progress.duration, int(progress.watched), progress.last_played_at),
                    )
            except sqlite3.IntegrityError as exc:
                raise NotFoundError(f"video {progress.video_id}") from exc

    def get_progress(self, video_id):
        row = self._one("SELECT * FROM progress WHERE video_id = ?", (video_id,))
        if row is None:
            return None
        data = dict(row)
        data["watched"] = bool(data["watched"])
        return from_dict(Progress, data)

    def delete_progress(self, video_id):
        with self._lock, self._db:
            self._db.execute("DELETE FROM progress WHERE video_id = ?", (video_id,))

    def clear_history(self):
        with self._lock, self._db:
            self._db.execute("DELETE FROM progress")

    def list_progress(self):
        out = []
        for row in self._all("SELECT * FROM progress"):
            data = dict(row)
            data["watched"] = bool(data["watched"])
            out.append(from_dict(Progress, data))
        return out

    def list_category_links(self):
        return [(r[0], r[1]) for r in self._all("SELECT video_id, category_id FROM video_categories")]

    def list_playlist_links(self):
        return [(r[0], r[1], r[2]) for r in self._all("SELECT playlist_id, video_id, position FROM playlist_items")]

    # migração e backup
    def export_data(self):
        data = empty_export()
        data["videos"] = [dict(r) for r in self._all("SELECT * FROM videos ORDER BY id")]
        data["categories"] = [dict(r) for r in self._all("SELECT * FROM categories ORDER BY id")]
        data["playlists"] = [dict(r) for r in self._all("SELECT * FROM playlists ORDER BY id")]
        data["video_categories"] = [[r[0], r[1]] for r in self._all("SELECT video_id, category_id FROM video_categories ORDER BY rowid")]
        data["playlist_items"] = [
            [r[0], r[1], r[2]] for r in self._all("SELECT playlist_id, video_id, position FROM playlist_items ORDER BY playlist_id, position")
        ]
        data["progress"] = [{**dict(r), "watched": bool(r["watched"])} for r in self._all("SELECT * FROM progress")]
        return data

    def _insert_all(self, data):
        for table, cols, rows in (
            ("videos", ["id"] + _VIDEO_COLS, data.get("videos", [])),
            ("categories", ["id"] + _CATEGORY_COLS, data.get("categories", [])),
            ("playlists", ["id"] + _PLAYLIST_COLS, data.get("playlists", [])),
        ):
            self._db.executemany(_insert(table, cols), [[row.get(c) for c in cols] for row in rows])
        self._db.executemany(
            "INSERT INTO video_categories (video_id, category_id) VALUES (?, ?)", data.get("video_categories", [])
        )
        self._db.executemany(
            "INSERT INTO playlist_items (playlist_id, video_id, position) VALUES (?, ?, ?)", data.get("playlist_items", [])
        )
        self._db.executemany(
            _insert("progress", _PROGRESS_COLS),
            [[int(r[c]) if c == "watched" else r.get(c) for c in _PROGRESS_COLS] for r in data.get("progress", [])],
        )

    def import_data(self, data):
        with self._lock:
            if not self.is_empty():
                raise StorageError("target_not_empty", str(self._path))
            if data.get("schema_version", 0) > SCHEMA_VERSION:
                raise StorageError("library_unsupported")
            data = normalize_export(data)
            try:
                with self._db:
                    self._insert_all(data)
            except sqlite3.IntegrityError as exc:
                raise StorageError("library_import_invalid", str(exc)) from exc

    def replace_data(self, data):
        with self._lock:
            if data.get("schema_version", 0) > SCHEMA_VERSION:
                raise StorageError("library_unsupported")
            data = normalize_export(data)
            try:
                with self._db:  # uma transação só: se algo falhar, nada foi apagado
                    for table in ("progress", "playlist_items", "video_categories", "playlists", "categories", "videos"):
                        self._db.execute(f"DELETE FROM {table}")
                    self._insert_all(data)
            except sqlite3.IntegrityError as exc:
                raise StorageError("library_import_invalid", str(exc)) from exc
