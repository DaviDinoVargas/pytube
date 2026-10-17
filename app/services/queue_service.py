from PySide6.QtCore import QObject, Signal

from app.domain.queue import PlayQueue


class QueueService(QObject):
    """Fila de reprodução do app, gravada nas preferências. Vídeos removidos da biblioteca saem da fila sozinhos."""

    changed = Signal()

    def __init__(self, library, settings):
        super().__init__()
        self._library = library
        self._settings = settings
        self._queue = PlayQueue(settings.queue_ids, settings.queue_current)
        library.changed.connect(self._on_library_changed)

    # -- consulta -----------------------------------------------------------------------------
    @property
    def ids(self):
        return self._queue.ids

    @property
    def current(self):
        return self._queue.current

    def __len__(self):
        return len(self._queue)

    def __contains__(self, video_id):
        return video_id in self._queue

    def videos(self):
        """Vídeos da fila, na ordem. Ids que não existem mais são descartados."""
        self._prune()
        out = []
        for video_id in self._queue.ids:
            video = self._library.get(video_id)
            if video is not None:
                out.append(video)
        return out

    def next_id(self, video_id=None):
        return self._queue.next_id(video_id)

    def previous_id(self, video_id=None):
        return self._queue.previous_id(video_id)

    # -- alteração ----------------------------------------------------------------------------
    def add(self, ids, play_next=False):
        self._queue.add([i for i in ids if self._library.get(i) is not None], play_next)
        self._commit()

    def remove(self, video_id):
        self._queue.remove(video_id)
        self._commit()

    def set_order(self, ids):
        self._queue.set_order(list(ids))
        self._commit()

    def set_current(self, video_id):
        """Marca o vídeo em reprodução. Fora da fila, só tira a marca (a fila continua igual)."""
        if video_id == self._queue.current:
            return
        self._queue.set_current(video_id)
        self._save()
        self.changed.emit()

    def clear(self):
        self._queue.clear()
        self._commit()

    # -- interno ------------------------------------------------------------------------------
    def _prune(self):
        if self._library.ready:
            self._queue.prune(v.id for v in self._library.store.list_videos())

    def _on_library_changed(self):
        before = self._queue.ids
        self._prune()
        if self._queue.ids != before:
            self._commit()

    def _save(self):
        self._settings.queue_ids = self._queue.ids
        self._settings.queue_current = self._queue.current

    def _commit(self):
        self._save()
        self.changed.emit()
