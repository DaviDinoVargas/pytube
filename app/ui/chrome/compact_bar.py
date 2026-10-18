from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton

from app.styles.icons import icon

MESSAGE_MS = 5000


class CompactBar(QFrame):
    """Cabeçalho da janela pequena (layout Compacto): menu ☰, título da página, colar link, fixar por cima e voltar à janela completa.
    Substitui a barra de link e a sidebar, que não cabem numa janela estreita."""

    paste_requested = Signal()
    pin_toggled = Signal(bool)
    full_requested = Signal()

    def __init__(self, translator, tokens):
        super().__init__()
        self.setObjectName("compactBar")
        self._tr = translator
        self._tokens = tokens
        self._title = ""
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(4)
        self.menu_button = self._button()
        self.menu_button.setPopupMode(QToolButton.InstantPopup)
        self.title_label = QLabel()
        self.title_label.setObjectName("compactTitle")
        self.paste_button = self._button()
        self.paste_button.clicked.connect(self.paste_requested)
        self.pin_button = self._button()
        self.pin_button.setCheckable(True)
        self.pin_button.toggled.connect(self.pin_toggled)
        self.full_button = self._button()
        self.full_button.clicked.connect(self.full_requested)
        row.addWidget(self.menu_button)
        row.addWidget(self.title_label, 1)
        for button in (self.paste_button, self.pin_button, self.full_button):
            row.addWidget(button)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(MESSAGE_MS)
        self._timer.timeout.connect(lambda: self.show_message(""))
        self.setFixedHeight(44)
        self.retranslate()

    def _button(self):
        button = QToolButton()
        button.setObjectName("iconButton")
        button.setCursor(Qt.PointingHandCursor)
        button.setIconSize(QSize(20, 20))
        return button

    def set_title(self, text):
        self._title = text
        if not self._timer.isActive():
            self._show(text)

    def _show(self, text, error=False):
        self.title_label.setProperty("error", error)
        self.title_label.style().unpolish(self.title_label)
        self.title_label.style().polish(self.title_label)
        self.title_label.setText(self.title_label.fontMetrics().elidedText(text, Qt.ElideRight, max(120, self.width() - 190)))
        self.title_label.setToolTip(text)

    def show_message(self, text, error=False):
        """Mensagem passageira no lugar do título; some sozinha e o título volta."""
        self._timer.stop()
        if text:
            self._show(text, error)
            self._timer.start()
        else:
            self._show(self._title)

    def set_pinned(self, pinned):
        self.pin_button.blockSignals(True)
        self.pin_button.setChecked(pinned)
        self.pin_button.blockSignals(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._show(self.title_label.toolTip() or self._title)

    def set_tokens(self, tokens):
        self._tokens = tokens
        color = tokens["text_primary"]
        self.menu_button.setIcon(icon("panel", color, 20))
        self.paste_button.setIcon(icon("link", color, 20))
        self.pin_button.setIcon(icon("pin", color, 20))
        self.full_button.setIcon(icon("maximize", color, 20))

    def retranslate(self):
        t = self._tr.t
        for button, key in ((self.menu_button, "compact.menu"), (self.paste_button, "compact.paste"),
                            (self.pin_button, "compact.pin_tip"), (self.full_button, "compact.full_tip")):
            button.setToolTip(t(key))
            button.setAccessibleName(t(key))
