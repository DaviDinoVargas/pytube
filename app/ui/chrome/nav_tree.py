from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QAbstractItemView, QFrame, QTreeWidget, QTreeWidgetItem, QVBoxLayout

from app.domain import query as q
from app.styles.icons import icon

TREE_WIDTH = 252
KIND, PAYLOAD = Qt.UserRole, Qt.UserRole + 1
SECTION, QUERY, PAGE, CATEGORY, PLAYLIST = "section", "query", "page", "category", "playlist"

LIBRARY_ENTRIES = (
    ("all", "tree.all", q.LibraryQuery(sort=q.SORT_NEWEST)),
    ("downloaded", "tree.downloaded", q.LibraryQuery(state=q.STATE_DOWNLOADED)),
    ("saved", "tree.saved", q.LibraryQuery(state=q.STATE_SAVED)),
    ("problems", "tree.problems", q.LibraryQuery(state=q.STATE_PROBLEMS)),
    ("in_progress", "tree.in_progress", q.LibraryQuery(watch=q.WATCH_IN_PROGRESS, sort=q.SORT_LAST_PLAYED)),
    ("unwatched", "tree.unwatched", q.LibraryQuery(watch=q.WATCH_UNWATCHED)),
)
TOOL_PAGES = (("playlists", "nav.playlists"), ("categories", "nav.categories"), ("history", "nav.history"), ("downloads", "nav.downloads"))


def _dot(color, size=12):
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(1, 1, size - 2, size - 2)
    painter.end()
    return QIcon(pix)


class NavTree(QFrame):
    """Navegação do layout Gerenciador: uma árvore (como o painel de pastas de um gerenciador de arquivos) com a biblioteca
    por estado, as categorias, as playlists e as ferramentas. Cada entrada mostra quantos vídeos tem."""

    query_requested = Signal(object)  # LibraryQuery
    page_requested = Signal(str)
    category_requested = Signal(int)
    playlist_requested = Signal(int)

    def __init__(self, translator, tokens):
        super().__init__()
        self.setObjectName("navTreeFrame")
        self.setFixedWidth(TREE_WIDTH)
        self._tr = translator
        self._tokens = tokens
        self._counts = {}
        self._data = None
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        self.tree = QTreeWidget()
        self.tree.setObjectName("navTree")
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(12)
        self.tree.setFrameShape(QFrame.NoFrame)
        self.tree.setIconSize(QSize(16, 16))
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree.setUniformRowHeights(True)
        self.tree.setAnimated(False)
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.itemClicked.connect(self._clicked)
        self.tree.itemActivated.connect(self._clicked)
        column.addWidget(self.tree)
        self._sections = {}
        self._items = {}
        self._expanded = {"library": True, "categories": True, "playlists": True, "tools": True}

    # -- construção ---------------------------------------------------------------------------------------
    def set_tokens(self, tokens):
        self._tokens = tokens
        self.rebuild()

    def refresh(self, data, counts):
        """`data`: LibraryData; `counts`: contagem por chave de entrada (library/<chave>, category/<id>, playlist/<id>, ...)."""
        self._data, self._counts = data, dict(counts)
        self.rebuild()

    def _section(self, key, label):
        item = QTreeWidgetItem([label.upper()])
        item.setData(0, KIND, SECTION)
        font = QFont(item.font(0))
        font.setBold(True)
        font.setPixelSize(11)
        item.setFont(0, font)
        item.setFlags(Qt.ItemIsEnabled)
        self.tree.addTopLevelItem(item)
        self._sections[key] = item
        return item

    def _leaf(self, parent, key, label, count, kind, payload, icon_name=None, color=None):
        text = f"{label}    {count}" if count is not None else label
        item = QTreeWidgetItem(parent, [text])
        item.setData(0, KIND, kind)
        item.setData(0, PAYLOAD, payload)
        item.setToolTip(0, label)
        if color:
            item.setIcon(0, _dot(color))
        elif icon_name:
            item.setIcon(0, icon(icon_name, self._tokens["text_secondary"], 16))
        self._items[key] = item
        return item

    def rebuild(self):
        t = self._tr.t
        selected = self.selected_key()
        self.tree.clear()
        self._sections, self._items = {}, {}
        library = self._section("library", t("tree.library"))
        for key, label_key, query in LIBRARY_ENTRIES:
            self._leaf(library, f"library/{key}", t(label_key), self._counts.get(f"library/{key}"), QUERY, query,
                       {"all": "library", "downloaded": "check", "saved": "bookmark", "problems": "warning",
                        "in_progress": "play", "unwatched": "history"}[key])
        categories = self._section("categories", t("nav.categories"))
        for category in (self._data.categories if self._data is not None else []):
            self._leaf(categories, f"category/{category.id}", category.name, self._counts.get(f"category/{category.id}"),
                       CATEGORY, category.id, "categories", category.color)
        playlists = self._section("playlists", t("nav.playlists"))
        for playlist in (self._data.playlists if self._data is not None else []):
            self._leaf(playlists, f"playlist/{playlist.id}", playlist.name, self._counts.get(f"playlist/{playlist.id}"),
                       PLAYLIST, playlist.id, "playlists")
        tools = self._section("tools", t("tree.tools"))
        for page, label_key in TOOL_PAGES:
            count = self._counts.get(f"page/{page}")
            self._leaf(tools, f"page/{page}", t(label_key), count if count else None, PAGE, page,
                       {"playlists": "playlists", "categories": "categories", "history": "history", "downloads": "downloads"}[page])
        for key, section in self._sections.items():
            section.setExpanded(self._expanded.get(key, True))
        if selected in self._items:
            self.select(selected)

    # -- seleção --------------------------------------------------------------------------------------------
    def selected_key(self):
        item = self.tree.currentItem()
        for key, candidate in self._items.items():
            if candidate is item:
                return key
        return None

    def select(self, key):
        item = self._items.get(key)
        self.tree.blockSignals(True)
        if item is None:
            self.tree.clearSelection()
            self.tree.setCurrentItem(None)
        else:
            self.tree.setCurrentItem(item)
        self.tree.blockSignals(False)

    def key_for_query(self, query):
        """Entrada da árvore que corresponde à consulta atual (ignora busca de texto e ordenação)."""
        base = q.LibraryQuery(state=query.state, watch=query.watch, category_ids=query.category_ids, playlist_id=query.playlist_id,
                              period=query.period, duration=query.duration, channel=query.channel)
        if query.playlist_id is not None and not query.category_ids and base.state == q.STATE_ALL:
            return f"playlist/{query.playlist_id}"
        if len(query.category_ids) == 1 and query.playlist_id is None and base.state == q.STATE_ALL and base.watch == q.WATCH_ALL:
            return f"category/{next(iter(query.category_ids))}"
        for key, _label, entry in LIBRARY_ENTRIES:
            if base == q.LibraryQuery(state=entry.state, watch=entry.watch):
                return f"library/{key}"
        return None

    def _clicked(self, item, _column=0):
        kind, payload = item.data(0, KIND), item.data(0, PAYLOAD)
        if kind == QUERY:
            self.query_requested.emit(payload)
        elif kind == PAGE:
            self.page_requested.emit(payload)
        elif kind == CATEGORY:
            self.category_requested.emit(payload)
        elif kind == PLAYLIST:
            self.playlist_requested.emit(payload)

    def keys(self):
        return list(self._items)

    def retranslate(self):
        self.rebuild()
