"""Busca, filtros e ordenação da biblioteca. Funções puras: recebem dados e devolvem a lista pronta."""

import unicodedata
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone

from app.domain import playback
from app.domain.models import LOCAL_INVALID, LOCAL_MISSING, LOCAL_OK

# estado do arquivo
STATE_ALL, STATE_DOWNLOADED, STATE_SAVED, STATE_PROBLEMS = "all", "downloaded", "saved", "problems"
STATES = (STATE_ALL, STATE_DOWNLOADED, STATE_SAVED, STATE_PROBLEMS)
# assistido
WATCH_ALL, WATCH_UNWATCHED, WATCH_IN_PROGRESS, WATCH_WATCHED = "all", "unwatched", "in_progress", "watched"
WATCHES = (WATCH_ALL, WATCH_UNWATCHED, WATCH_IN_PROGRESS, WATCH_WATCHED)
# período em que foi adicionado
PERIOD_ANY, PERIOD_7, PERIOD_30, PERIOD_365 = "any", "7d", "30d", "365d"
PERIODS = {PERIOD_ANY: None, PERIOD_7: 7, PERIOD_30: 30, PERIOD_365: 365}
# duração
DURATION_ANY, DURATION_SHORT, DURATION_MEDIUM, DURATION_LONG = "any", "short", "medium", "long"
DURATIONS = (DURATION_ANY, DURATION_SHORT, DURATION_MEDIUM, DURATION_LONG)
SHORT_LIMIT, LONG_LIMIT = 4 * 60, 20 * 60
# ordenação
SORT_NEWEST, SORT_OLDEST = "newest", "oldest"
SORT_TITLE_AZ, SORT_TITLE_ZA = "title_az", "title_za"
SORT_DURATION_DESC, SORT_DURATION_ASC = "duration_desc", "duration_asc"
SORT_LAST_PLAYED, SORT_PROGRESS, SORT_DOWNLOAD = "last_played", "progress", "download_state"
SORTS = (
    SORT_NEWEST, SORT_OLDEST, SORT_TITLE_AZ, SORT_TITLE_ZA, SORT_DURATION_DESC, SORT_DURATION_ASC,
    SORT_LAST_PLAYED, SORT_PROGRESS, SORT_DOWNLOAD,
)


def fold(text):
    """Texto para comparação: minúsculo e sem acentos ('Ação' == 'acao')."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().strip()


@dataclass(frozen=True)
class LibraryQuery:
    text: str = ""
    state: str = STATE_ALL
    category_ids: frozenset = field(default_factory=frozenset)
    playlist_id: int | None = None
    watch: str = WATCH_ALL
    period: str = PERIOD_ANY
    duration: str = DURATION_ANY
    sort: str = SORT_NEWEST

    def active_filters(self):
        """Filtros ligados, como (chave, valor), para mostrar chips removíveis. Texto e ordenação ficam de fora."""
        active = []
        if self.state != STATE_ALL:
            active.append(("state", self.state))
        for category_id in sorted(self.category_ids):
            active.append(("category", category_id))
        if self.playlist_id is not None:
            active.append(("playlist", self.playlist_id))
        if self.watch != WATCH_ALL:
            active.append(("watch", self.watch))
        if self.period != PERIOD_ANY:
            active.append(("period", self.period))
        if self.duration != DURATION_ANY:
            active.append(("duration", self.duration))
        return active

    def without(self, key, value=None):
        """Cópia sem um filtro (o 'x' de um chip)."""
        if key == "state":
            return replace(self, state=STATE_ALL)
        if key == "category":
            return replace(self, category_ids=self.category_ids - {value})
        if key == "playlist":
            return replace(self, playlist_id=None)
        if key == "watch":
            return replace(self, watch=WATCH_ALL)
        if key == "period":
            return replace(self, period=PERIOD_ANY)
        if key == "duration":
            return replace(self, duration=DURATION_ANY)
        return self

    def cleared(self):
        """'Limpar filtros': mantém busca e ordenação."""
        return replace(
            self, state=STATE_ALL, category_ids=frozenset(), playlist_id=None, watch=WATCH_ALL,
            period=PERIOD_ANY, duration=DURATION_ANY,
        )

    @property
    def is_filtered(self):
        return bool(self.text.strip()) or bool(self.active_filters())


@dataclass
class LibraryData:
    """Tudo que a consulta precisa, já carregado: evita ir ao banco por vídeo."""

    videos: list
    categories: list = field(default_factory=list)
    category_links: list = field(default_factory=list)  # (video_id, category_id)
    playlists: list = field(default_factory=list)
    playlist_links: list = field(default_factory=list)  # (playlist_id, video_id, position)
    progress: dict = field(default_factory=dict)  # video_id -> Progress

    def categories_of(self, video_id):
        return {c for v, c in self.category_links if v == video_id}


def _state_ok(video, state):
    if state == STATE_ALL:
        return True
    if state == STATE_DOWNLOADED:
        return video.local_status == LOCAL_OK
    if state == STATE_SAVED:
        return video.local_status not in (LOCAL_OK, LOCAL_MISSING, LOCAL_INVALID)
    if state == STATE_PROBLEMS:
        return video.local_status in (LOCAL_MISSING, LOCAL_INVALID)
    return True


def _watch_ok(progress, watch):
    if watch == WATCH_ALL:
        return True
    if watch == WATCH_WATCHED:
        return bool(progress and progress.watched)
    started = bool(progress and not progress.watched and progress.position >= playback.RESUME_MIN)
    if watch == WATCH_IN_PROGRESS:
        return started
    return not (progress and progress.watched) and not started  # unwatched


def _duration_ok(video, duration):
    if duration == DURATION_ANY:
        return True
    if not video.duration:
        return False
    if duration == DURATION_SHORT:
        return video.duration <= SHORT_LIMIT  # curto: até 4 min
    if duration == DURATION_LONG:
        return video.duration > LONG_LIMIT  # longo: mais de 20 min
    return SHORT_LIMIT < video.duration <= LONG_LIMIT  # médio: entre 4 e 20 min


def _period_ok(video, period, now):
    days = PERIODS.get(period)
    if days is None:
        return True
    try:
        added = datetime.fromisoformat(video.added_at)
    except (TypeError, ValueError):
        return False
    if added.tzinfo is None:
        added = added.replace(tzinfo=timezone.utc)
    return added >= now - timedelta(days=days)


def _fraction(video, progress):
    total = (progress.duration if progress and progress.duration else None) or video.duration
    if not progress or not total:
        return 0.0
    return 1.0 if progress.watched else min(1.0, progress.position / total)


def search_text_of(video, data, category_names, playlist_names):
    parts = [video.title, video.channel, video.url, video.source_id]
    parts += [category_names.get(c, "") for c in data.categories_of(video.id)]
    parts += [playlist_names.get(p, "") for p, v, _pos in data.playlist_links if v == video.id]
    return fold(" ".join(parts))


def apply_query(query, data, now=None):
    """Filtra e ordena os vídeos. Todos os filtros se combinam com E; várias categorias combinam com OU."""
    now = now or datetime.now(timezone.utc)
    category_names = {c.id: c.name for c in data.categories}
    playlist_names = {p.id: p.name for p in data.playlists}
    needle_words = [fold(w) for w in query.text.split() if w.strip()]
    in_playlist = None
    order_in_playlist = {}
    if query.playlist_id is not None:
        order_in_playlist = {v: pos for p, v, pos in data.playlist_links if p == query.playlist_id}
        in_playlist = set(order_in_playlist)
    links_by_video = {}
    for v, c in data.category_links:
        links_by_video.setdefault(v, set()).add(c)

    result = []
    for video in data.videos:
        if in_playlist is not None and video.id not in in_playlist:
            continue
        if not _state_ok(video, query.state):
            continue
        if query.category_ids and not (links_by_video.get(video.id, set()) & query.category_ids):
            continue
        progress = data.progress.get(video.id)
        if not _watch_ok(progress, query.watch):
            continue
        if not _duration_ok(video, query.duration) or not _period_ok(video, query.period, now):
            continue
        if needle_words:
            haystack = search_text_of(video, data, category_names, playlist_names)
            if not all(word in haystack for word in needle_words):
                continue
        result.append(video)

    if query.playlist_id is not None and query.sort == SORT_NEWEST:
        result.sort(key=lambda v: order_in_playlist[v.id])  # numa playlist, a ordem escolhida é a padrão
        return result
    return _sort(result, query.sort, data.progress)


def _sort(videos, sort, progress_map):
    if sort == SORT_OLDEST:
        return sorted(videos, key=lambda v: (v.added_at, v.id or 0))
    if sort == SORT_TITLE_AZ:
        return sorted(videos, key=lambda v: (fold(v.title), v.id or 0))
    if sort == SORT_TITLE_ZA:
        return sorted(videos, key=lambda v: (fold(v.title), v.id or 0), reverse=True)
    if sort == SORT_DURATION_DESC:
        return sorted(videos, key=lambda v: (-(v.duration or 0), v.id or 0))
    if sort == SORT_DURATION_ASC:
        return sorted(videos, key=lambda v: (v.duration is None, v.duration or 0, v.id or 0))
    if sort == SORT_LAST_PLAYED:
        played = [v for v in videos if v.id in progress_map]
        never = [v for v in videos if v.id not in progress_map]
        played.sort(key=lambda v: progress_map[v.id].last_played_at, reverse=True)
        return played + sorted(never, key=lambda v: (v.added_at, v.id or 0), reverse=True)
    if sort == SORT_PROGRESS:
        return sorted(videos, key=lambda v: (-_fraction(v, progress_map.get(v.id)), v.id or 0))
    if sort == SORT_DOWNLOAD:
        rank = {LOCAL_OK: 0, LOCAL_MISSING: 1, LOCAL_INVALID: 1}
        return sorted(videos, key=lambda v: (rank.get(v.local_status, 2), -(v.id or 0)))
    return sorted(videos, key=lambda v: (v.added_at, v.id or 0), reverse=True)  # newest
