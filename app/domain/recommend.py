"""Recomendações locais: sugestões feitas só com os dados da própria biblioteca (nada vai para a internet).
Funções puras sobre `LibraryData`."""

from app.domain import query as q
from app.domain.history import watch_status, WATCH_DONE, WATCH_PROGRESS
from app.domain.models import LOCAL_OK


def last_watched(data):
    """O vídeo reproduzido mais recentemente (ou None)."""
    entries = [(data.progress[v.id].last_played_at, v) for v in data.videos if v.id in data.progress]
    return max(entries, key=lambda e: e[0])[1] if entries else None


def featured(data):
    """Vídeo em destaque: o que está em andamento mais recente; senão o mais novo ainda não visto; senão o mais novo."""
    in_progress = q.apply_query(q.LibraryQuery(watch=q.WATCH_IN_PROGRESS, sort=q.SORT_LAST_PLAYED), data)
    if in_progress:
        return in_progress[0]
    unwatched = q.apply_query(q.LibraryQuery(watch=q.WATCH_UNWATCHED, sort=q.SORT_NEWEST), data)
    if unwatched:
        return unwatched[0]
    newest = q.apply_query(q.LibraryQuery(sort=q.SORT_NEWEST), data)
    return newest[0] if newest else None


def related(video, data, limit=12):
    """Vídeos parecidos com `video`: mesmas categorias (peso 3), mesma playlist e mesmo canal (peso 2).
    Os ainda não assistidos e os já baixados sobem na lista. Sem nada em comum, não entra."""
    categories = data.categories_of(video.id)
    playlists = {p for p, v, _pos in data.playlist_links if v == video.id}
    in_playlist = {}
    for p, v, _pos in data.playlist_links:
        in_playlist.setdefault(v, set()).add(p)
    scored = []
    for other in data.videos:
        if other.id == video.id:
            continue
        score = 3 * len(categories & data.categories_of(other.id))
        score += 2 * bool(playlists & in_playlist.get(other.id, set()))
        score += 2 * bool(video.channel and other.channel == video.channel)
        if not score:
            continue
        status = watch_status(data.progress.get(other.id))
        score += 1 if status != WATCH_DONE else 0
        score += 0.5 if other.local_status == LOCAL_OK else 0
        scored.append((score, other.added_at, other))
    scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
    return [s[2] for s in scored[:limit]]


def because_you_watched(data, limit=12):
    """(vídeo de referência, sugestões) a partir do último assistido. Sem sugestões, devolve (None, [])."""
    base = last_watched(data)
    if base is None:
        return None, []
    suggestions = [v for v in related(base, data, limit * 2) if watch_status(data.progress.get(v.id)) != WATCH_DONE]
    return (base, suggestions[:limit]) if suggestions else (None, [])


def resume_label_position(video, data):
    """Segundos em que o vídeo parou, se ele está em andamento; senão 0."""
    progress = data.progress.get(video.id)
    return progress.position if watch_status(progress) == WATCH_PROGRESS else 0.0
