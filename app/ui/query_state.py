from dataclasses import replace

from PySide6.QtCore import QObject, Signal

from app.domain.query import LibraryQuery


class QueryState(QObject):
    """Consulta atual da biblioteca, compartilhada: a busca da barra superior e a página da biblioteca editam a mesma."""

    changed = Signal()

    def __init__(self, settings):
        super().__init__()
        self._settings = settings
        self._query = LibraryQuery(sort=settings.library_sort)

    @property
    def query(self):
        return self._query

    def set_query(self, query):
        if query == self._query:
            return
        if query.sort != self._query.sort:
            self._settings.library_sort = query.sort  # a ordenação escolhida é lembrada
        self._query = query
        self.changed.emit()

    def set_text(self, text):
        self.set_query(replace(self._query, text=text))

    def set_sort(self, sort):
        self.set_query(replace(self._query, sort=sort))

    def remove_filter(self, key, value=None):
        self.set_query(self._query.without(key, value))

    def clear_filters(self):
        self.set_query(self._query.cleared())

    def clear_all(self):
        self.set_query(replace(self._query.cleared(), text=""))

    def focus(self, **changes):
        """Zera os filtros e aplica `changes` (ex.: abrir a biblioteca já filtrada por uma categoria)."""
        base = replace(self._query.cleared(), text="")
        self.set_query(replace(base, **changes))
