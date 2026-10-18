from dataclasses import replace

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QComboBox, QFrame, QLabel, QLineEdit, QMenu, QPushButton, QToolButton, QVBoxLayout, QWidget

from app.domain import query as q
from app.ui.widgets.flow_layout import FlowLayout


class FilterBar(QFrame):
    """Filtros avançados em uma barra fixa no topo (layout Gerenciador). Faz o mesmo que o painel suspenso da biblioteca e
    mais um filtro por canal; cada alteração vale na hora."""

    changed = Signal(object)  # LibraryQuery

    def __init__(self, translator):
        super().__init__()
        self.setObjectName("filterBar")
        self._tr = translator
        self._query = q.LibraryQuery()
        self._categories = []
        self._playlists = []
        self._fields = []  # (rótulo, widget, chave de texto)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 6)
        box = QWidget()
        self._flow = FlowLayout(box, 10, 6)
        outer.addWidget(box)

        self.state_combo = self._combo("filter.state")
        self.watch_combo = self._combo("filter.watch")
        self.period_combo = self._combo("filter.period")
        self.duration_combo = self._combo("filter.duration")
        self.playlist_combo = self._combo("filter.playlist")
        self.categories_button = QToolButton()
        self.categories_button.setObjectName("playerMenuButton")
        self.categories_button.setPopupMode(QToolButton.InstantPopup)
        self.categories_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.categories_button.setMenu(QMenu(self.categories_button))
        self._field("filter.categories", self.categories_button)
        self.channel_edit = QLineEdit()
        self.channel_edit.setClearButtonEnabled(True)
        self.channel_edit.setMinimumWidth(160)
        self.channel_edit.setMaximumWidth(220)
        self._channel_timer = QTimer(self)
        self._channel_timer.setSingleShot(True)
        self._channel_timer.setInterval(250)
        self._channel_timer.timeout.connect(self._emit)
        self.channel_edit.textChanged.connect(lambda _t: self._channel_timer.start())
        self._field("filter.channel", self.channel_edit)
        self.clear_button = QPushButton()
        self.clear_button.setObjectName("secondary")
        self.clear_button.setCursor(Qt.PointingHandCursor)
        self.clear_button.clicked.connect(lambda: self.changed.emit(self._query.cleared()))
        self._flow.addWidget(self.clear_button)
        self._fill_static()
        self.retranslate()

    # -- construção ----------------------------------------------------------------------------
    def _field(self, label_key, widget):
        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(2)
        label = QLabel()
        label.setObjectName("cardMeta")
        label.setProperty("key", label_key)
        column.addWidget(label)
        column.addWidget(widget)
        self._flow.addWidget(holder)
        self._fields.append((label, widget))
        widget.label = label

    def _combo(self, label_key):
        combo = QComboBox()
        combo.setMinimumWidth(110)
        combo.setMaximumWidth(170)
        combo.activated.connect(lambda _i: self._emit())
        self._field(label_key, combo)
        return combo

    def _fill_static(self):
        t = self._tr.t
        for combo, prefix, values in (
            (self.state_combo, "filter.state_", q.STATES), (self.watch_combo, "filter.watch_", q.WATCHES),
            (self.period_combo, "filter.period_", tuple(q.PERIODS)), (self.duration_combo, "filter.duration_", q.DURATIONS),
        ):
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for value in values:
                combo.addItem(t(prefix + value), value)
            combo.setCurrentIndex(max(0, combo.findData(current)))
            combo.blockSignals(False)

    # -- dados ----------------------------------------------------------------------------------
    def set_options(self, categories, playlists):
        t = self._tr.t
        self._categories, self._playlists = list(categories), list(playlists)
        self.playlist_combo.blockSignals(True)
        self.playlist_combo.clear()
        self.playlist_combo.addItem(t("filter.playlist_any"), None)
        for playlist in playlists:
            self.playlist_combo.addItem(playlist.name, playlist.id)
        self.playlist_combo.blockSignals(False)
        menu = self.categories_button.menu()
        menu.clear()
        self._category_actions = {}
        if not self._categories:
            menu.addAction(t("filter.no_categories")).setEnabled(False)
        for category in self._categories:
            action = menu.addAction(category.name)
            action.setCheckable(True)
            action.toggled.connect(lambda _c: self._emit())
            self._category_actions[category.id] = action
        self.set_query(self._query)

    def set_query(self, query):
        """Mostra `query` nos controles sem disparar `changed`."""
        self._query = query
        for combo, value in (
            (self.state_combo, query.state), (self.watch_combo, query.watch), (self.period_combo, query.period),
            (self.duration_combo, query.duration), (self.playlist_combo, query.playlist_id),
        ):
            combo.blockSignals(True)
            combo.setCurrentIndex(max(0, combo.findData(value)))
            combo.blockSignals(False)
        for category_id, action in getattr(self, "_category_actions", {}).items():
            action.blockSignals(True)
            action.setChecked(category_id in query.category_ids)
            action.blockSignals(False)
        if self.channel_edit.text().strip() != query.channel.strip():
            self.channel_edit.blockSignals(True)
            self.channel_edit.setText(query.channel)
            self.channel_edit.blockSignals(False)
        self._update_categories_text()

    def _update_categories_text(self):
        count = len(self._query.category_ids)
        base = self._tr.t("filter.categories")
        self.categories_button.setText(f"{base} ({count}) ▾" if count else f"{base} ▾")

    def _emit(self):
        query = replace(
            self._query,
            state=self.state_combo.currentData(), watch=self.watch_combo.currentData(),
            period=self.period_combo.currentData(), duration=self.duration_combo.currentData(),
            playlist_id=self.playlist_combo.currentData(), channel=self.channel_edit.text(),
            category_ids=frozenset(cid for cid, action in getattr(self, "_category_actions", {}).items() if action.isChecked()),
        )
        self._query = query
        self._update_categories_text()
        self.changed.emit(query)

    def retranslate(self):
        t = self._tr.t
        for label, widget in self._fields:
            label.setText(t(label.property("key")))
            widget.setAccessibleName(t(label.property("key")))
        self.clear_button.setText(t("filter.clear"))
        self._fill_static()
        self.set_options(self._categories, self._playlists)
