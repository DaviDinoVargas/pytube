from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.domain.query import SORTS
from app.domain.states import video_state
from app.styles.icons import icon
from app.ui.pages.base import EmptyState
from app.ui.pages.video_pages import VideoPage
from app.ui.widgets.chip_bar import ChipBar
from app.ui.widgets.filter_panel import FilterPanel
from app.ui.widgets.flow_layout import FlowLayout
from app.ui.widgets.video_grid import VideoGrid
from app.ui.widgets.video_row import VideoRow


class RowList(QWidget):
    """Linhas empilhadas (visualização em lista)."""

    def __init__(self):
        super().__init__()
        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(8)
        self.rows = []

    def set_rows(self, rows):
        for row in self.rows:
            row.setParent(None)
            row.deleteLater()
        self.rows = list(rows)
        for row in self.rows:
            self._column.addWidget(row)


class LibraryPage(VideoPage):
    """Biblioteca completa: busca, filtros, ordenação, grade ou lista e ações em lote."""

    key = "library"
    message = Signal(str, bool)

    def __init__(self, translator, library, tokens, org, state, settings, **kwargs):
        self._org = org
        self._state = state
        self._settings = settings
        self._selecting = False
        self._selected = set()
        self._shown = []
        self._view = settings.library_view
        super().__init__(translator, library, tokens, **kwargs)

        # barra de ferramentas
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.count_label = QLabel()
        self.count_label.setObjectName("cardMeta")
        bar.addWidget(self.count_label, 1)
        self.select_button = QToolButton()
        self.select_button.setObjectName("toolbarToggle")
        self.select_button.setCheckable(True)
        self.select_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.select_button.toggled.connect(self.set_selecting)
        bar.addWidget(self.select_button)
        self.view_group = QButtonGroup(self)
        self.grid_button, self.list_button = QToolButton(), QToolButton()
        for button, mode, name in ((self.grid_button, "grid", "panel"), (self.list_button, "list", "playlists")):
            button.setObjectName("toolbarToggle")
            button.setCheckable(True)
            button.setIconSize(QSize(18, 18))
            button.setProperty("mode", mode)
            button.setProperty("iconName", name)
            self.view_group.addButton(button)
            button.clicked.connect(lambda _=False, m=mode: self.set_view(m))
            bar.addWidget(button)
        self.sort_combo = QComboBox()
        self.sort_combo.activated.connect(lambda _i: self._state.set_sort(self.sort_combo.currentData()))
        bar.addWidget(self.sort_combo)
        self.filter_button = QPushButton()
        self.filter_button.setObjectName("secondary")
        self.filter_button.setCursor(Qt.PointingHandCursor)
        self.filter_button.clicked.connect(self._show_filters)
        bar.addWidget(self.filter_button)
        self.body.insertLayout(0, bar)

        self.panel = FilterPanel(translator)
        self.panel.changed.connect(self._state.set_query)

        self.chips = ChipBar(translator)
        self.chips.remove_requested.connect(self._state.remove_filter)
        self.chips.text_removed.connect(lambda: self._state.set_text(""))
        self.chips.clear_requested.connect(self._state.clear_all)
        self.body.insertWidget(1, self.chips)

        # ações em lote
        self.bulk_bar = QFrame()
        self.bulk_bar.setObjectName("bulkBar")
        bulk = QHBoxLayout(self.bulk_bar)
        bulk.setContentsMargins(14, 8, 10, 8)
        bulk.setSpacing(8)
        self.selected_label = QLabel()
        self.select_all_button = QPushButton()
        self.select_all_button.setObjectName("linkButton")
        self.select_all_button.clicked.connect(self.select_all)
        self.categories_button = QToolButton()
        self.playlist_button = QToolButton()
        for button in (self.categories_button, self.playlist_button):
            button.setObjectName("playerMenuButton")
            button.setPopupMode(QToolButton.InstantPopup)
            button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.remove_button = QPushButton()
        self.remove_button.setObjectName("secondary")
        self.remove_button.clicked.connect(self.remove_selected)
        self.done_button = QPushButton()
        self.done_button.setObjectName("primary")
        self.done_button.clicked.connect(lambda: self.select_button.setChecked(False))
        bulk.addWidget(self.selected_label)
        bulk.addWidget(self.select_all_button)
        bulk.addStretch(1)
        for widget in (self.categories_button, self.playlist_button, self.remove_button, self.done_button):
            bulk.addWidget(widget)
        self.bulk_bar.hide()
        self.body.insertWidget(2, self.bulk_bar)

        self.no_results = EmptyState(translator, "library_no_results")
        self.no_results_clear = QPushButton()
        self.no_results_clear.setObjectName("primary")
        self.no_results_clear.clicked.connect(self._state.clear_all)
        self.no_results.layout().insertWidget(3, self.no_results_clear, 0, Qt.AlignCenter)
        self.no_results.hide()
        self.body.addWidget(self.no_results)

        self._fixed_items = self.body.count()
        state.changed.connect(self._on_state_changed)
        self.retranslate()

    # ------------------------------------------------------------------------------------
    # dados
    # ------------------------------------------------------------------------------------
    def videos(self):
        return self._org.query(self._state.query)

    def refresh(self):
        self._dirty = False
        videos = self.videos()
        self._shown = videos
        self._selected &= {v.id for v in videos}
        self._update_controls()
        self.render(videos)

    def _on_state_changed(self):
        self._update_controls()
        self.mark_dirty()

    # ------------------------------------------------------------------------------------
    # renderização
    # ------------------------------------------------------------------------------------
    def render(self, videos):
        self._clear_body()
        query = self._state.query
        library_empty = not self._library.list_videos()
        self.empty.setVisible(not videos and library_empty)
        self.no_results.setVisible(not videos and not library_empty)
        self.no_results_clear.setVisible(query.is_filtered)
        if not videos:
            return
        if self._view == "list":
            widget = RowList()
            widget.set_rows([self._make_row(v) for v in videos])
        else:
            widget = self.make_grid(videos)
        self._apply_selection_mode(widget)
        self.body.addWidget(widget)
        self.body.addStretch(1)

    def make_card(self, video):
        card = super().make_card(video)
        card.selection_changed.connect(self._on_selection)
        return card

    def _make_row(self, video):
        video = self._library.validate_local(video)
        by_video = self._categories_by_video()
        row = VideoRow(
            self._tr, self._tokens, video, video_state(video, self._download_status(video.id)), self._library.thumbnail_path(video),
            can_download=self._can_download(), organize=self._organize, categories=by_video.get(video.id, ()),
        )
        row.open_requested.connect(self.video_opened)
        row.action_requested.connect(self.video_action)
        row.selection_changed.connect(self._on_selection)
        return row

    def _categories_by_video(self):
        info = {c.id: (c.name, c.color) for c in self._org.categories()}
        out = {}
        for video_id, category_id in self._org.store.list_category_links():
            if category_id in info:
                out.setdefault(video_id, []).append(info[category_id])
        return out

    def _clear_body(self):
        while self.body.count() > self._fixed_items:  # fixos: barra, chips, ações em lote, estados vazios
            item = self.body.takeAt(self._fixed_items)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def cards(self):
        return [c for g in self.findChildren(VideoGrid) for c in g.cards]

    def rows(self):
        return [r for lst in self.findChildren(RowList) for r in lst.rows]

    def items(self):
        return self.cards() + self.rows()

    # ------------------------------------------------------------------------------------
    # controles
    # ------------------------------------------------------------------------------------
    def _update_controls(self):
        t = self._tr.t
        query = self._state.query
        n = len(self._shown)
        self.count_label.setText(t("library.count_one") if n == 1 else t("library.count_many", count=n))
        self.sort_combo.blockSignals(True)
        self.sort_combo.setCurrentIndex(max(0, self.sort_combo.findData(query.sort)))
        self.sort_combo.blockSignals(False)
        self.panel.set_query(query)
        self.panel.set_options(self._org.categories(), self._org.playlists())
        category_names = {c.id: c.name for c in self._org.categories()}
        playlist_names = {p.id: p.name for p in self._org.playlists()}
        self.chips.set_query(query, category_names, playlist_names)
        active = len(query.active_filters())
        self.filter_button.setText(t("filter.button") + (f"  ({active})" if active else ""))
        self.grid_button.setChecked(self._view == "grid")
        self.list_button.setChecked(self._view == "list")
        self._update_bulk()

    def _show_filters(self):
        self.panel.set_query(self._state.query)
        self.panel.adjustSize()
        self.panel.move(self.filter_button.mapToGlobal(self.filter_button.rect().bottomRight()) - self.panel.rect().topRight())
        self.panel.show()

    def set_view(self, mode):
        if mode != self._view:
            self._view = mode
            self._settings.library_view = mode
        self.grid_button.setChecked(mode == "grid")
        self.list_button.setChecked(mode == "list")
        self.mark_dirty()

    # ------------------------------------------------------------------------------------
    # seleção e ações em lote
    # ------------------------------------------------------------------------------------
    @property
    def selected_ids(self):
        return sorted(self._selected)

    def set_selecting(self, selecting):
        self._selecting = bool(selecting)
        if not self._selecting:
            self._selected.clear()
        if self.select_button.isChecked() != self._selecting:
            self.select_button.setChecked(self._selecting)
        for item in self.items():
            item.set_selectable(self._selecting)
        self._update_bulk()

    def _apply_selection_mode(self, widget):
        items = widget.cards if isinstance(widget, VideoGrid) else widget.rows
        for item in items:
            item.set_selectable(self._selecting)
            if item.video.id in self._selected:
                item.set_selected(True)

    def _on_selection(self, video_id, selected):
        (self._selected.add if selected else self._selected.discard)(video_id)
        self._update_bulk()

    def select_all(self):
        for item in self.items():
            item.set_selected(True)

    def _update_bulk(self):
        t = self._tr.t
        n = len(self._selected)
        self.bulk_bar.setVisible(self._selecting)
        self.selected_label.setText(t("library.selected_one") if n == 1 else t("library.selected_many", count=n))
        for button in (self.categories_button, self.playlist_button, self.remove_button):
            button.setEnabled(n > 0)
        self._fill_bulk_menus()

    def _fill_bulk_menus(self):
        if self._organize is None:
            return
        ids = self.selected_ids
        self.categories_button.setMenu(self._organize.categories_menu(ids, self.categories_button))
        self.playlist_button.setMenu(self._organize.playlists_menu(ids, self.playlist_button))

    def remove_selected(self):
        ids = self.selected_ids
        if not ids:
            return
        if not self._confirm_remove(len(ids)):
            return
        for video_id in ids:
            self._library.remove(video_id)  # nunca apaga o arquivo local
        self._selected.clear()
        self.message.emit(self._tr.t("bulk.removed_toast"), False)

    def _confirm_remove(self, count):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(self._tr.t("bulk.confirm_title"))
        box.setText(self._tr.t("bulk.confirm_body", count=count))
        remove = box.addButton(self._tr.t("bulk.remove"), QMessageBox.AcceptRole)
        box.addButton(self._tr.t("storage.cancel"), QMessageBox.RejectRole)
        box.exec()
        return box.clickedButton() is remove

    # ------------------------------------------------------------------------------------
    # tema e idioma
    # ------------------------------------------------------------------------------------
    def set_tokens(self, tokens):
        self._tokens = tokens
        for button in (self.grid_button, self.list_button):
            button.setIcon(icon(button.property("iconName"), tokens["text_primary"], 18))
        super().set_tokens(tokens)

    def retranslate(self):
        super().retranslate()
        if not hasattr(self, "sort_combo"):
            return
        t = self._tr.t
        self.select_button.setText(t("library.select"))
        self.grid_button.setToolTip(t("library.view_grid"))
        self.grid_button.setAccessibleName(t("library.view_grid"))
        self.list_button.setToolTip(t("library.view_list"))
        self.list_button.setAccessibleName(t("library.view_list"))
        self.sort_combo.blockSignals(True)
        self.sort_combo.clear()
        for sort in SORTS:
            self.sort_combo.addItem(t(f"sort.{sort}"), sort)
        self.sort_combo.setAccessibleName(t("library.sort"))
        self.sort_combo.blockSignals(False)
        self.select_all_button.setText(t("library.select_all"))
        self.categories_button.setText(t("bulk.categories") + " ▾")
        self.playlist_button.setText(t("bulk.playlist") + " ▾")
        self.remove_button.setText(t("bulk.remove"))
        self.done_button.setText(t("library.select_done"))
        self.no_results.retranslate()
        self.no_results_clear.setText(t("filter.clear"))
        self.panel.retranslate()
        self._update_controls()
