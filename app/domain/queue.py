"""Fila de reprodução: lista ordenada de ids de vídeo com um item atual. Lógica pura, sem Qt."""


class PlayQueue:
    def __init__(self, ids=(), current=None):
        self._ids = []
        for video_id in ids:
            if video_id not in self._ids:
                self._ids.append(video_id)
        self._current = current if current in self._ids else None

    # -- consulta ----------------------------------------------------------------------------
    @property
    def ids(self):
        return list(self._ids)

    @property
    def current(self):
        return self._current

    def __len__(self):
        return len(self._ids)

    def __contains__(self, video_id):
        return video_id in self._ids

    def position(self, video_id):
        """Posição (a partir de 0) do vídeo na fila, ou None."""
        return self._ids.index(video_id) if video_id in self._ids else None

    def next_id(self, video_id=None):
        """O que vem depois de `video_id` (padrão: o atual). Sem atual, o primeiro. No fim, None."""
        video_id = self._current if video_id is None else video_id
        if video_id not in self._ids:
            return self._ids[0] if self._ids and self._current is None else None
        index = self._ids.index(video_id) + 1
        return self._ids[index] if index < len(self._ids) else None

    def previous_id(self, video_id=None):
        video_id = self._current if video_id is None else video_id
        if video_id not in self._ids:
            return None
        index = self._ids.index(video_id) - 1
        return self._ids[index] if index >= 0 else None

    # -- alteração -----------------------------------------------------------------------------
    def add(self, ids, play_next=False):
        """Põe no fim da fila (ou logo depois do atual). Quem já está na fila só muda de lugar."""
        ids = [i for n, i in enumerate(ids) if i not in ids[:n]]
        for video_id in ids:
            if video_id in self._ids and video_id != self._current:
                self._ids.remove(video_id)
        ids = [i for i in ids if i != self._current]
        if play_next and self._current in self._ids:
            at = self._ids.index(self._current) + 1
            self._ids[at:at] = ids
        else:
            self._ids.extend(ids)

    def remove(self, video_id):
        if video_id not in self._ids:
            return
        if video_id == self._current:
            self._current = None
        self._ids.remove(video_id)

    def move(self, video_id, new_index):
        if video_id not in self._ids:
            return
        self._ids.remove(video_id)
        self._ids.insert(max(0, min(new_index, len(self._ids))), video_id)

    def set_order(self, ids):
        """Reordena pelo que a tela mostra (ids desconhecidos são ignorados; os que faltarem vão para o fim)."""
        known = [i for i in ids if i in self._ids]
        self._ids = known + [i for i in self._ids if i not in known]

    def set_current(self, video_id):
        """Marca o vídeo atual. Um vídeo que não está na fila apenas deixa a fila sem atual."""
        self._current = video_id if video_id in self._ids else None

    def clear(self):
        self._ids, self._current = [], None

    def prune(self, existing):
        """Tira da fila os ids que não existem mais (vídeos removidos da biblioteca)."""
        existing = set(existing)
        self._ids = [i for i in self._ids if i in existing]
        if self._current not in self._ids:
            self._current = None
