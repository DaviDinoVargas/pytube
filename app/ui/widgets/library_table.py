from dataclasses import dataclass

from PySide6.QtCore import QAbstractTableModel, QByteArray, QItemSelectionModel, QModelIndex, QSortFilterProxyModel, Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QMenu, QTableView

from app.domain import states
from app.domain.states import format_duration
from app.services.storage_service import format_bytes
from app.ui.widgets.video_card import format_added

COLUMNS = ("title", "channel", "duration", "categories", "added", "state", "quality", "size", "file", "progress")
DEFAULT_COLUMNS = ("title", "duration", "categories", "added", "state", "file")
SORT_ROLE = Qt.UserRole + 1
ID_ROLE = Qt.UserRole + 2
NUMERIC = {"duration", "size", "progress"}


@dataclass
class TableRow:
    video: object
    state: str
    categories: str
    added: str
    file: str
    fraction: float


class LibraryTableModel(QAbstractTableModel):
    def __init__(self, translator):
        super().__init__()
        self._tr = translator
        self._rows = []
        self.columns = list(DEFAULT_COLUMNS)  # só as colunas visíveis, na ordem em que aparecem

    def set_rows(self, rows):
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def row_at(self, index):
        return self._rows[index] if 0 <= index < len(self._rows) else None

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole and 0 <= section < len(self.columns):
            return self._tr.t(f"table.col_{self.columns[section]}")
        return None

    def set_columns(self, columns):
        self.beginResetModel()
        self.columns = [c for c in COLUMNS if c in columns] or list(DEFAULT_COLUMNS)
        self.endResetModel()

    # -- valores --------------------------------------------------------------------------------
    def _text(self, row, column):
        t, v = self._tr.t, row.video
        if column == "title":
            return v.title
        if column == "channel":
            return v.channel or "—"
        if column == "duration":
            return format_duration(v.duration) or "—"
        if column == "categories":
            return row.categories or "—"
        if column == "added":
            return row.added or "—"
        if column == "state":
            return {
                states.SAVED: t("table.state_saved"), states.DOWNLOADED: "✓ " + t("card.state_downloaded"),
            }.get(row.state, "⚠ " + t(f"card.state_{row.state}"))
        if column == "quality":
            return (v.local_quality or "—") if v.local_status == "ok" else "—"
        if column == "size":
            return format_bytes(v.local_size) if v.local_size else "—"
        if column == "file":
            return row.file or "—"
        return f"{round(row.fraction * 100)}%" if row.fraction else "—"

    def _sort_key(self, row, column):
        v = row.video
        if column == "title":
            return (v.title or "").casefold()
        if column == "channel":
            return (v.channel or "").casefold()
        if column == "duration":
            return v.duration or 0
        if column == "categories":
            return row.categories.casefold()
        if column == "added":
            return v.added_at
        if column == "state":
            return {states.DOWNLOADED: 0}.get(row.state, 1 if row.state != states.SAVED else 2)
        if column == "quality":
            return int((v.local_quality or "0").rstrip("p").split()[0] or 0) if (v.local_quality or "0")[0].isdigit() else 0
        if column == "size":
            return v.local_size or 0
        if column == "file":
            return row.file.casefold()
        return row.fraction

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row, column = self._rows[index.row()], self.columns[index.column()]
        if role == Qt.DisplayRole:
            return self._text(row, column)
        if role == SORT_ROLE:
            return self._sort_key(row, column)
        if role == ID_ROLE:
            return row.video.id
        if role == Qt.ToolTipRole:
            return row.file if column == "file" and row.file else self._text(row, column)
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignRight | Qt.AlignVCenter) if column in NUMERIC else int(Qt.AlignLeft | Qt.AlignVCenter)
        return None


class LibraryTable(QTableView):
    """Tabela da biblioteca (milhares de linhas): colunas escolhíveis, ordenação pelos cabeçalhos, seleção múltipla,
    abrir com duplo clique/Enter e menu de contexto."""

    open_requested = Signal(int)
    action_requested = Signal(list, str)  # ids, ação (download, browser, folder, watch, unwatch, remove)
    selection_ids_changed = Signal(list)
    columns_changed = Signal(list)

    def __init__(self, translator, organize=None):
        super().__init__()
        self.setObjectName("libraryTable")
        self._tr = translator
        self._organize = organize
        self._model = LibraryTableModel(translator)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(SORT_ROLE)
        self.setModel(self._proxy)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(False)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.ElideMiddle)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(34)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._row_menu)
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionsMovable(True)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSortIndicator(-1, Qt.AscendingOrder)  # sem ordenação própria: vale a ordem escolhida na barra da biblioteca
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self._columns_menu)
        self.doubleClicked.connect(lambda index: self._open(index))
        self.selectionModel().selectionChanged.connect(lambda *_: self.selection_ids_changed.emit(self.selected_ids()))
        self.setMinimumHeight(320)
        self._apply_widths()

    # -- dados ---------------------------------------------------------------------------------
    def set_rows(self, rows):
        self._model.set_rows(rows)

    @property
    def columns(self):
        return list(self._model.columns)

    def set_columns(self, columns):
        self._model.set_columns(columns)
        self._apply_widths()
        self.columns_changed.emit(self.columns)

    def _apply_widths(self):
        header = self.horizontalHeader()
        widths = {"title": 380, "channel": 160, "duration": 80, "categories": 180, "added": 120, "state": 150,
                  "quality": 90, "size": 90, "file": 300, "progress": 90}
        for i, column in enumerate(self._model.columns):
            header.setSectionResizeMode(i, QHeaderView.Interactive)
            self.setColumnWidth(i, widths.get(column, 120))

    def selected_ids(self):
        rows = {i.row() for i in self.selectionModel().selectedRows()}
        return sorted(self._proxy.index(r, 0).data(ID_ROLE) for r in rows)

    def select_ids(self, ids):
        wanted = set(ids)
        model = self.selectionModel()
        model.clearSelection()
        flags = QItemSelectionModel.Select | QItemSelectionModel.Rows
        for r in range(self._proxy.rowCount()):
            if self._proxy.index(r, 0).data(ID_ROLE) in wanted:
                model.select(self._proxy.index(r, 0), flags)

    def video_ids(self):
        return [self._proxy.index(r, 0).data(ID_ROLE) for r in range(self._proxy.rowCount())]

    def sort_state(self):
        header = self.horizontalHeader()
        return header.sortIndicatorSection(), header.sortIndicatorOrder()

    def clear_sort(self):
        self.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
        self._proxy.sort(-1)

    # -- cabeçalho salvo ---------------------------------------------------------------------------
    def header_state(self):
        return bytes(self.horizontalHeader().saveState().toBase64()).decode("ascii")

    def restore_header_state(self, text):
        if text:
            self.horizontalHeader().restoreState(QByteArray.fromBase64(text.encode("ascii")))

    # -- interação --------------------------------------------------------------------------------
    def _open(self, index):
        video_id = index.siblingAtColumn(0).data(ID_ROLE)
        if video_id is not None:
            self.open_requested.emit(video_id)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and self.currentIndex().isValid():
            self._open(self.currentIndex())
            return
        super().keyPressEvent(event)

    def _columns_menu(self, pos):
        self.build_columns_menu().exec(self.horizontalHeader().mapToGlobal(pos))

    def build_columns_menu(self):
        menu = QMenu(self)
        for column in COLUMNS:
            action = menu.addAction(self._tr.t(f"table.col_{column}"))
            action.setCheckable(True)
            action.setChecked(column in self._model.columns)
            action.setEnabled(column != "title")  # o título é sempre visível
            action.triggered.connect(lambda checked, c=column: self._toggle_column(c, checked))
        return menu

    def _toggle_column(self, column, visible):
        current = set(self._model.columns)
        (current.add if visible else current.discard)(column)
        self.set_columns(current)

    def _row_menu(self, pos):
        index = self.indexAt(pos)
        if not index.isValid():
            return
        if not self.selectionModel().isRowSelected(index.row(), QModelIndex()):
            self.selectRow(index.row())
        menu = self.build_row_menu(index)
        if menu is not None:
            menu.exec(self.viewport().mapToGlobal(pos))

    def build_row_menu(self, index):
        """Menu de contexto da linha `index` (ou da seleção, se a linha faz parte dela)."""
        ids = self.selected_ids()
        if not ids:
            return None
        t = self._tr.t
        row = self._model.row_at(self._proxy.mapToSource(index).row())
        menu = QMenu(self)
        single = len(ids) == 1
        if single:
            menu.addAction(t("card.menu_open")).triggered.connect(lambda: self.open_requested.emit(ids[0]))
            if row is not None and row.state in (states.SAVED, states.MISSING, states.INVALID, states.FAILED):
                menu.addAction(t("card.menu_download")).triggered.connect(lambda: self.action_requested.emit(ids, "download"))
            menu.addAction(t("card.menu_browser")).triggered.connect(lambda: self.action_requested.emit(ids, "browser"))
        menu.addAction(t("queue.add")).triggered.connect(lambda: self.action_requested.emit(ids, "queue_add"))
        menu.addAction(t("queue.play_next")).triggered.connect(lambda: self.action_requested.emit(ids, "queue_next"))
        if single:
            if row is not None and row.state == states.DOWNLOADED:
                menu.addAction(t("card.menu_folder")).triggered.connect(lambda: self.action_requested.emit(ids, "folder"))
            menu.addSeparator()
        for key, label in (("watch", "card.menu_watched"), ("unwatch", "card.menu_unwatched")):
            menu.addAction(t(label)).triggered.connect(lambda _=False, k=key: self.action_requested.emit(ids, k))
        if self._organize is not None:
            menu.addMenu(self._organize.categories_menu(ids, menu))
            menu.addMenu(self._organize.playlists_menu(ids, menu))
        menu.addSeparator()
        menu.addAction(t("card.menu_remove")).triggered.connect(lambda: self.action_requested.emit(ids, "remove"))
        return menu
