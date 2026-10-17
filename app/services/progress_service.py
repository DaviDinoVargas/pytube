from app.domain import playback
from app.domain.models import Progress, now_iso


class ProgressService:
    """Posição de reprodução e estado 'assistido' de cada vídeo da biblioteca."""

    def __init__(self, library):
        self._library = library

    def get(self, video_id):
        return self._library.store.get_progress(video_id) if self._library.ready else None

    def save(self, video_id, position, duration=None):
        """Grava a posição. Ao passar de 95% marca como assistido (e volta a posição ao início)."""
        if not self._library.ready:
            return None
        previous = self._library.store.get_progress(video_id)
        total = duration or (previous.duration if previous else None)
        watched = bool(previous and previous.watched) or playback.is_watched(position, total)
        progress = Progress(
            video_id=video_id,
            position=0.0 if playback.is_watched(position, total) else float(position),
            duration=float(total) if total else None,
            watched=watched,
            last_played_at=now_iso(),
        )
        self._library.store.save_progress(progress)
        self._library.notify()
        return progress

    def resume_position(self, video_id, duration=None):
        return playback.resume_position(self.get(video_id), duration)

    def mark_watched(self, video_id, watched=True):
        progress = self.get(video_id) or Progress(video_id=video_id)
        progress.watched = watched
        progress.position = 0.0
        progress.last_played_at = now_iso()
        self._library.store.save_progress(progress)
        self._library.notify()

    def restart(self, video_id):
        """'Recomeçar do início': zera a posição e tira a marca de assistido."""
        progress = self.get(video_id)
        if progress is not None:
            progress.position, progress.watched = 0.0, False
            self._library.store.save_progress(progress)
            self._library.notify()

    def forget(self, video_id):
        """Tira o vídeo do histórico (esquece posição e 'assistido'). O vídeo continua na biblioteca."""
        if self._library.ready:
            self._library.store.delete_progress(video_id)
            self._library.notify()

    def clear_all(self):
        """Limpa o histórico inteiro. Biblioteca, categorias e arquivos não são tocados."""
        if self._library.ready:
            self._library.store.clear_history()
            self._library.notify()
