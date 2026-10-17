import re

from app.domain.errors import NotFoundError, StorageError
from app.domain.models import Category, Playlist
from app.domain.query import LibraryData, apply_query

MAX_NAME = 60
_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def clean_name(name):
    text = " ".join((name or "").split())
    if not text:
        raise StorageError("name_empty")
    if len(text) > MAX_NAME:
        raise StorageError("name_too_long", str(len(text)))
    return text


def clean_color(color):
    if color in (None, ""):
        return None
    if not _COLOR.match(color):
        raise StorageError("color_invalid", str(color))
    return color.upper()


class OrganizationService:
    """Categorias, playlists e a consulta (busca, filtros e ordenação) da biblioteca."""

    def __init__(self, library):
        self._library = library

    @property
    def store(self):
        return self._library.store

    # -- consulta -------------------------------------------------------------------
    def load_data(self):
        if not self._library.ready:
            return LibraryData(videos=[])
        store = self.store
        return LibraryData(
            videos=store.list_videos(),
            categories=store.list_categories(),
            category_links=store.list_category_links(),
            playlists=store.list_playlists(),
            playlist_links=store.list_playlist_links(),
            progress={p.video_id: p for p in store.list_progress()},
        )

    def query(self, query):
        if not self._library.ready:
            return []
        return apply_query(query, self.load_data())

    # -- categorias -----------------------------------------------------------------
    def categories(self):
        return self.store.list_categories() if self._library.ready else []

    def get_category(self, category_id):
        return next((c for c in self.categories() if c.id == category_id), None)

    def create_category(self, name, description="", color=None):
        category = self.store.add_category(Category(clean_name(name), (description or "").strip(), clean_color(color)))
        self._library.notify()
        return category

    def update_category(self, category_id, name, description="", color=None):
        category = self.get_category(category_id)
        if category is None:
            raise NotFoundError(f"category {category_id}")
        category.name, category.description, category.color = clean_name(name), (description or "").strip(), clean_color(color)
        self.store.update_category(category)
        self._library.notify()
        return category

    def delete_category(self, category_id):
        """Apaga só a categoria: os vídeos continuam na biblioteca."""
        self.store.delete_category(category_id)
        self._library.notify()

    def category_counts(self):
        if not self._library.ready:
            return {}
        counts = {}
        for _video_id, category_id in self.store.list_category_links():
            counts[category_id] = counts.get(category_id, 0) + 1
        return counts

    def video_category_ids(self, video_id):
        if not self._library.ready:
            return []
        return self.store.get_video_category_ids(video_id)

    def assign_categories(self, video_ids, add=(), remove=()):
        """Atribui/retira categorias de vários vídeos de uma vez. Um vídeo pode ter várias."""
        add, remove = set(add), set(remove)
        for video_id in video_ids:
            current = set(self.store.get_video_category_ids(video_id))
            updated = (current | add) - remove
            if updated != current:
                ordered = [c for c in self.store.get_video_category_ids(video_id) if c in updated]
                ordered += sorted(updated - current)
                self.store.set_video_categories(video_id, ordered)
        self._library.notify()

    # -- playlists -------------------------------------------------------------------
    def playlists(self):
        return self.store.list_playlists() if self._library.ready else []

    def get_playlist(self, playlist_id):
        return next((p for p in self.playlists() if p.id == playlist_id), None)

    def create_playlist(self, name, description=""):
        playlist = self.store.add_playlist(Playlist(clean_name(name), (description or "").strip()))
        self._library.notify()
        return playlist

    def update_playlist(self, playlist_id, name, description=""):
        playlist = self.get_playlist(playlist_id)
        if playlist is None:
            raise NotFoundError(f"playlist {playlist_id}")
        playlist.name, playlist.description = clean_name(name), (description or "").strip()
        self.store.update_playlist(playlist)
        self._library.notify()
        return playlist

    def delete_playlist(self, playlist_id):
        """Apaga só a playlist: nem os vídeos nem os arquivos locais são tocados."""
        self.store.delete_playlist(playlist_id)
        self._library.notify()

    def playlist_counts(self):
        if not self._library.ready:
            return {}
        counts = {}
        for playlist_id, _video_id, _pos in self.store.list_playlist_links():
            counts[playlist_id] = counts.get(playlist_id, 0) + 1
        return counts

    def playlist_video_ids(self, playlist_id):
        if not self._library.ready:
            return []
        return self.store.get_playlist_items(playlist_id)

    def playlist_videos(self, playlist_id):
        if not self._library.ready:
            return []
        videos = {v.id: v for v in self.store.list_videos()}
        return [videos[i] for i in self.store.get_playlist_items(playlist_id) if i in videos]

    def add_to_playlist(self, playlist_id, video_ids):
        """Acrescenta ao fim, sem repetir os que já estão."""
        current = self.store.get_playlist_items(playlist_id)
        extra = [v for v in dict.fromkeys(video_ids) if v not in current]
        if extra:
            self.store.set_playlist_items(playlist_id, current + extra)
            self._library.notify()
        return len(extra)

    def remove_from_playlist(self, playlist_id, video_ids):
        drop = set(video_ids)
        current = self.store.get_playlist_items(playlist_id)
        kept = [v for v in current if v not in drop]
        if len(kept) != len(current):
            self.store.set_playlist_items(playlist_id, kept)
            self._library.notify()

    def move_in_playlist(self, playlist_id, video_id, new_index):
        items = self.store.get_playlist_items(playlist_id)
        if video_id not in items:
            raise NotFoundError(f"video {video_id} na playlist {playlist_id}")
        items.remove(video_id)
        items.insert(max(0, min(new_index, len(items))), video_id)
        self.store.set_playlist_items(playlist_id, items)
        self._library.notify()

    def next_in_playlist(self, playlist_id, video_id):
        items = self.store.get_playlist_items(playlist_id)
        if video_id not in items or items.index(video_id) + 1 >= len(items):
            return None
        return self._library.get(items[items.index(video_id) + 1])
