from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QToolButton, QVBoxLayout

from app.domain import layouts
from app.domain.urls import extract_video_id
from app.styles.icons import icon

STREAMING_TABS = ("home", "library", "playlists", "categories", "history", "downloads")
CINEMA_TABS = ("home", "library", "playlists")
MESSAGE_MS = 6000


class LinkPopup(QFrame):
    """Campo para colar o link do vídeo: aparece sob o botão '+ Link' da navegação do topo."""

    video_requested = Signal(str)

    def __init__(self, translator):
        super().__init__(None, Qt.Popup)
        self.setObjectName("linkPopup")
        self._tr = translator
        column = QVBoxLayout(self)
        column.setContentsMargins(14, 12, 14, 12)
        column.setSpacing(8)
        row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setMinimumWidth(360)
        self.url_input.setClearButtonEnabled(True)
        self.url_input.returnPressed.connect(self._submit)
        self.url_input.textChanged.connect(lambda _t: self.set_error(""))
        self.open_button = QPushButton()
        self.open_button.setObjectName("primary")
        self.open_button.setCursor(Qt.PointingHandCursor)
        self.open_button.clicked.connect(self._submit)
        row.addWidget(self.url_input, 1)
        row.addWidget(self.open_button)
        column.addLayout(row)
        self.error_label = QLabel()
        self.error_label.setObjectName("statusError")
        self.error_label.hide()
        column.addWidget(self.error_label)
        self.retranslate()

    def set_error(self, text):
        self.error_label.setText(text)
        self.error_label.setVisible(bool(text))
        self.url_input.setProperty("invalid", bool(text))
        self.url_input.style().unpolish(self.url_input)
        self.url_input.style().polish(self.url_input)

    def _submit(self):
        text = self.url_input.text().strip()
        if not text:
            return
        video_id = extract_video_id(text)
        if video_id is None:
            self.set_error(self._tr.t("topbar.invalid_url"))
            return
        self.set_error("")
        self.hide()
        self.url_input.clear()
        self.video_requested.emit(video_id)

    def popup_below(self, widget):
        self.adjustSize()
        corner = widget.mapToGlobal(widget.rect().bottomRight())
        self.move(corner.x() - self.width(), corner.y() + 6)
        self.show()
        self.url_input.setFocus()
        self.url_input.selectAll()

    def retranslate(self):
        t = self._tr.t
        self.url_input.setPlaceholderText(t("topbar.url_placeholder"))
        self.url_input.setAccessibleName(t("topbar.url_placeholder"))
        self.open_button.setText(t("topbar.open"))


class TopNav(QFrame):
    """Navegação em abas no topo (layouts Streaming e Cinema): marca, abas, busca e '+ Link'. Substitui a sidebar."""

    page_selected = Signal(str)
    video_requested = Signal(str)
    search_changed = Signal(str)

    def __init__(self, translator, tokens):
        super().__init__()
        self.setObjectName("topNav")
        self._tr = translator
        self._tokens = tokens
        self._style = layouts.TOPNAV_STREAMING
        self._tabs = {}
        row = QHBoxLayout(self)
        row.setContentsMargins(24, 0, 20, 0)
        row.setSpacing(4)
        self.brand = QLabel("DinoTube")
        self.brand.setObjectName("topBrand")
        row.addWidget(self.brand)
        row.addSpacing(22)
        self._tabs_row = QHBoxLayout()
        self._tabs_row.setSpacing(2)
        row.addLayout(self._tabs_row)
        for key in STREAMING_TABS:
            button = QToolButton()
            button.setObjectName("topTab")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setFocusPolicy(Qt.TabFocus)
            button.clicked.connect(lambda _=False, k=key: self.page_selected.emit(k))
            self._tabs[key] = button
            self._tabs_row.addWidget(button)
        row.addSpacing(12)
        self.feedback = QLabel()
        self.feedback.setObjectName("statusOk")
        self.feedback.hide()
        row.addWidget(self.feedback, 1)
        row.addStretch(1)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("topSearch")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedWidth(250)
        self.search_input.textChanged.connect(self.search_changed)
        self._search_action = self.search_input.addAction(icon("search", tokens["text_secondary"], 18), QLineEdit.LeadingPosition)
        row.addWidget(self.search_input)
        self.add_button = QPushButton()
        self.add_button.setObjectName("primary")
        self.add_button.setCursor(Qt.PointingHandCursor)
        self.add_button.setIconSize(QSize(16, 16))
        self.popup = LinkPopup(translator)
        self.popup.video_requested.connect(self.video_requested)
        self.add_button.clicked.connect(lambda: self.popup.popup_below(self.add_button))
        row.addWidget(self.add_button)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(MESSAGE_MS)
        self._timer.timeout.connect(lambda: self.show_message(""))
        self.setFixedHeight(58)
        self.set_style(layouts.TOPNAV_STREAMING)
        self.retranslate()

    # -- estilo e seleção --------------------------------------------------------------------------
    def set_style(self, style):
        """'streaming': todas as abas, busca e botão; 'cinema': poucas abas, translúcido, discreto."""
        self._style = style
        tabs = CINEMA_TABS if style == layouts.TOPNAV_CINEMA else STREAMING_TABS
        for key, button in self._tabs.items():
            button.setVisible(key in tabs)
        self.setProperty("navStyle", style)
        self.style().unpolish(self)
        self.style().polish(self)
        self.search_input.setFixedWidth(200 if style == layouts.TOPNAV_CINEMA else 250)

    def select(self, key):
        """Marca a aba da página atual (páginas sem aba, como Configurações, desmarcam todas)."""
        key = {"playlist": "playlists", "watch": None}.get(key, key)
        button = self._tabs.get(key)
        if button is not None:
            button.setChecked(True)
            return
        for b in self._tabs.values():
            b.setAutoExclusive(False)
            b.setChecked(False)
            b.setAutoExclusive(True)

    @property
    def tabs(self):
        return dict(self._tabs)

    # -- mesma interface da barra clássica -------------------------------------------------------------
    @property
    def url_input(self):
        return self.popup.url_input

    def focus_url(self):
        self.popup.popup_below(self.add_button)

    def focus_search(self):
        self.search_input.setFocus()
        self.search_input.selectAll()

    def show_message(self, text, error=False):
        self.feedback.setObjectName("statusError" if error else "statusOk")
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)
        self.feedback.setText(text)
        self.feedback.setVisible(bool(text))
        self._timer.stop()
        if text:
            self._timer.start()

    def set_tokens(self, tokens):
        self._tokens = tokens
        self._search_action.setIcon(icon("search", tokens["text_secondary"], 18))
        self.add_button.setIcon(icon("link", tokens["text_on_accent"], 16))

    def retranslate(self):
        t = self._tr.t
        for key, button in self._tabs.items():
            button.setText(t(f"nav.{key}"))
            button.setAccessibleName(t(f"nav.{key}"))
        self.search_input.setPlaceholderText(t("topbar.search_placeholder"))
        self.search_input.setAccessibleName(t("topbar.search_placeholder"))
        for button in self.search_input.findChildren(QToolButton):
            button.setAccessibleName(t("topbar.clear"))
            button.setToolTip(t("topbar.clear"))
        self.add_button.setText(" " + t("topnav.add_link"))
        self.add_button.setAccessibleName(t("topnav.add_link"))
        self.popup.retranslate()
