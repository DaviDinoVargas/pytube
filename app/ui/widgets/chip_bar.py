from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPushButton, QToolButton, QWidget

from app.ui.widgets.flow_layout import FlowLayout


class ChipBar(QWidget):
    """Filtros ativos como chips removíveis, mais 'Limpar filtros'."""

    remove_requested = Signal(str, object)  # chave, valor
    text_removed = Signal()
    clear_requested = Signal()

    def __init__(self, translator):
        super().__init__()
        self._tr = translator
        self._flow = FlowLayout(self, 8, 6)
        self.chips = []
        self.hide()

    def labels_for(self, query, category_names, playlist_names):
        t = self._tr.t
        out = []
        if query.text.strip():
            out.append(("text", None, t("filter.chip_text", text=query.text.strip())))
        for key, value in query.active_filters():
            if key == "category":
                label = category_names.get(value, "?")
            elif key == "playlist":
                label = playlist_names.get(value, "?")
            elif key == "channel":
                label = t("filter.chip_channel", channel=value)
            else:
                label = t(f"filter.{key}_{value}")
            out.append((key, value, label))
        return out

    def set_query(self, query, category_names, playlist_names):
        while self._flow.count():
            item = self._flow.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.chips = []
        labels = self.labels_for(query, category_names, playlist_names)
        for key, value, label in labels:
            chip = QToolButton()
            chip.setObjectName("chip")
            chip.setText(f"{label}   ✕")
            chip.setCursor(Qt.PointingHandCursor)
            chip.setToolTip(self._tr.t("filter.chip_remove", name=label))
            chip.setAccessibleName(self._tr.t("filter.chip_remove", name=label))
            chip.clicked.connect(lambda _=False, k=key, v=value: self._removed(k, v))
            self._flow.addWidget(chip)
            self.chips.append(chip)
        if len(labels) > 1 or query.active_filters():
            clear = QPushButton(self._tr.t("filter.clear"))
            clear.setObjectName("linkButton")
            clear.setCursor(Qt.PointingHandCursor)
            clear.clicked.connect(self.clear_requested)
            self._flow.addWidget(clear)
            self.chips.append(clear)
        self.setVisible(bool(labels))
        self._flow.invalidate()

    def _removed(self, key, value):
        if key == "text":
            self.text_removed.emit()
        else:
            self.remove_requested.emit(key, value)
