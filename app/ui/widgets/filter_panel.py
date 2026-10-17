from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QFrame, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from app.domain import query as q


class FilterPanel(QFrame):
    """Painel suspenso com os filtros. Cada alteração do usuário é aplicada na hora (sem botão 'aplicar')."""

    changed = Signal(object)  # LibraryQuery

    def __init__(self, translator):
        super().__init__(None, Qt.Popup)
        self.setObjectName("filterPanel")
        self._tr = translator
        self._query = q.LibraryQuery()
        self._categories = []
        self._playlists = []
        self._category_checks = {}
        self.setMinimumWidth(300)

        column = QVBoxLayout(self)
        column.setContentsMargins(16, 14, 16, 14)
        column.setSpacing(6)
        self.state_combo = self._add_combo(column, "filter.state")
        self.watch_combo = self._add_combo(column, "filter.watch")
        self.period_combo = self._add_combo(column, "filter.period")
        self.duration_combo = self._add_combo(column, "filter.duration")
        self.playlist_combo = self._add_combo(column, "filter.playlist")
        self.categories_label = QLabel()
        self.categories_label.setObjectName("fieldLabel")
        column.addWidget(self.categories_label)
        self.categories_box = QWidget()
        self.categories_layout = QVBoxLayout(self.categories_box)
        self.categories_layout.setContentsMargins(0, 0, 0, 0)
        self.categories_layout.setSpacing(2)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMaximumHeight(140)
        scroll.setWidget(self.categories_box)
        column.addWidget(scroll)
        self.clear_button = QPushButton()
        self.clear_button.setObjectName("secondary")
        self.clear_button.setCursor(Qt.PointingHandCursor)
        self.clear_button.clicked.connect(lambda: self.changed.emit(self._query.cleared()))
        column.addSpacing(6)
        column.addWidget(self.clear_button)
        self._fill_static_combos()
        self.retranslate()

    # -- construção ----------------------------------------------------------------------
    def _add_combo(self, column, label_key):
        label = QLabel()
        label.setObjectName("fieldLabel")
        label.setProperty("key", label_key)
        combo = QComboBox()
        combo.activated.connect(lambda _i: self._emit())
        column.addWidget(label)
        column.addWidget(combo)
        combo.label = label
        return combo

    def _fill_static_combos(self):
        t = self._tr.t
        for combo, prefix, values in (
            (self.state_combo, "filter.state_", q.STATES),
            (self.watch_combo, "filter.watch_", q.WATCHES),
            (self.period_combo, "filter.period_", tuple(q.PERIODS)),
            (self.duration_combo, "filter.duration_", q.DURATIONS),
        ):
            current = combo.currentData()
            combo.clear()
            for value in values:
                combo.addItem(t(prefix + value), value)
            combo.setCurrentIndex(max(0, combo.findData(current)))

    # -- dados ------------------------------------------------------------------------------
    def set_options(self, categories, playlists):
        t = self._tr.t
        self._categories, self._playlists = list(categories), list(playlists)
        current = self.playlist_combo.currentData()
        self.playlist_combo.blockSignals(True)
        self.playlist_combo.clear()
        self.playlist_combo.addItem(t("filter.playlist_any"), None)
        for playlist in playlists:
            self.playlist_combo.addItem(playlist.name, playlist.id)
        self.playlist_combo.setCurrentIndex(max(0, self.playlist_combo.findData(current)))
        self.playlist_combo.blockSignals(False)
        while self.categories_layout.count():
            item = self.categories_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self._category_checks = {}
        if not self._categories:
            empty = QLabel(t("filter.no_categories"))
            empty.setObjectName("cardMeta")
            self.categories_layout.addWidget(empty)
        for category in self._categories:
            check = QCheckBox(category.name)
            check.toggled.connect(lambda _c: self._emit())
            self.categories_layout.addWidget(check)
            self._category_checks[category.id] = check
        self.set_query(self._query)

    def set_query(self, query):
        """Mostra `query` nos controles sem disparar `changed`."""
        self._query = query
        for combo, value in (
            (self.state_combo, query.state), (self.watch_combo, query.watch),
            (self.period_combo, query.period), (self.duration_combo, query.duration),
            (self.playlist_combo, query.playlist_id),
        ):
            combo.blockSignals(True)
            combo.setCurrentIndex(max(0, combo.findData(value)))
            combo.blockSignals(False)
        for category_id, check in self._category_checks.items():
            check.blockSignals(True)
            check.setChecked(category_id in query.category_ids)
            check.blockSignals(False)

    def _emit(self):
        query = replace(
            self._query,
            state=self.state_combo.currentData(),
            watch=self.watch_combo.currentData(),
            period=self.period_combo.currentData(),
            duration=self.duration_combo.currentData(),
            playlist_id=self.playlist_combo.currentData(),
            category_ids=frozenset(cid for cid, check in self._category_checks.items() if check.isChecked()),
        )
        self._query = query
        self.changed.emit(query)

    def retranslate(self):
        t = self._tr.t
        for combo in (self.state_combo, self.watch_combo, self.period_combo, self.duration_combo, self.playlist_combo):
            combo.label.setText(t(combo.label.property("key")))
        self.categories_label.setText(t("filter.categories"))
        self.clear_button.setText(t("filter.clear"))
        self._fill_static_combos()
        self.set_options(self._categories, self._playlists)
