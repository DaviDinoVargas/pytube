"""Histórico de reprodução e playlists inteligentes. Funções puras sobre os dados já carregados."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from app.domain import playback
from app.domain import query as q

# Playlists inteligentes: não são gravadas, são consultas sempre atualizadas.
SMART_PLAYLISTS = {
    "continue": q.LibraryQuery(watch=q.WATCH_IN_PROGRESS, sort=q.SORT_LAST_PLAYED),
    "unwatched": q.LibraryQuery(watch=q.WATCH_UNWATCHED, sort=q.SORT_NEWEST),
    "downloaded": q.LibraryQuery(state=q.STATE_DOWNLOADED, sort=q.SORT_DOWNLOAD),
    "recent": q.LibraryQuery(period=q.PERIOD_7, sort=q.SORT_NEWEST),
}
SMART_ORDER = ("continue", "unwatched", "downloaded", "recent")

WATCH_NONE, WATCH_PROGRESS, WATCH_DONE = "none", "in_progress", "watched"


def watch_status(progress):
    """'watched', 'in_progress' (começou e passou do mínimo) ou 'none'."""
    if progress is None:
        return WATCH_NONE
    if progress.watched:
        return WATCH_DONE
    return WATCH_PROGRESS if progress.position >= playback.RESUME_MIN else WATCH_NONE


def progress_fraction(video, progress):
    """0..1 do quanto foi assistido (1 se terminou)."""
    if progress is None:
        return 0.0
    if progress.watched:
        return 1.0
    total = progress.duration or video.duration
    if not total:
        return 0.0
    return max(0.0, min(1.0, progress.position / total))


@dataclass(frozen=True)
class HistoryEntry:
    video: object
    progress: object


def history_entries(data):
    """Vídeos já reproduzidos, do mais recente para o mais antigo."""
    entries = [HistoryEntry(v, data.progress[v.id]) for v in data.videos if v.id in data.progress]
    entries.sort(key=lambda e: e.progress.last_played_at, reverse=True)
    return entries


def _local_day(iso):
    try:
        moment = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone().date()


def group_by_day(entries, today=None):
    """Agrupa em ('today' | 'yesterday' | date) mantendo a ordem. Datas ilegíveis vão para o fim, em 'unknown'."""
    today = today or datetime.now().astimezone().date()
    groups, order = {}, []
    for entry in entries:
        day = _local_day(entry.progress.last_played_at)
        if day is None:
            key = "unknown"
        elif day == today:
            key = "today"
        elif day == today - timedelta(days=1):
            key = "yesterday"
        else:
            key = day
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(entry)
    order.sort(key=lambda k: (k == "unknown",))  # estável: 'unknown' por último
    return [(key, groups[key]) for key in order]
