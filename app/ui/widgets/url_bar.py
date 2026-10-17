from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QToolButton, QVBoxLayout, QWidget

from app.domain.urls import extract_video_id
from app.styles.icons import icon


class TopBar(QFrame):
    """Barra superior: link do vídeo à esquerda, pesquisa da biblioteca à direita."""

    video_requested = Signal(str)
    search_changed = Signal(str)

    def __init__(self, translator, tokens):
        super().__init__()
        self.setObjectName("topbar")
        self._tr = translator
        self._tokens = tokens
        self._compact = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 12, 20, 8)
        outer.setSpacing(4)

        row = QHBoxLayout()
        row.setSpacing(12)
        self.menu_button = QToolButton()  # só no layout Compacto, onde não há sidebar
        self.menu_button.setObjectName("iconButton")
        self.menu_button.setPopupMode(QToolButton.InstantPopup)
        self.menu_button.setCursor(Qt.PointingHandCursor)
        self.menu_button.setIconSize(QSize(20, 20))
        self.menu_button.hide()
        row.addWidget(self.menu_button)
        self.url_input = QLineEdit()
        self.url_input.setClearButtonEnabled(True)
        self.url_input.setMinimumWidth(280)
        self.url_input.returnPressed.connect(self._submit)
        self.url_input.textChanged.connect(self._clear_error)
        self.open_button = QPushButton()
        self.open_button.setObjectName("primary")
        self.open_button.setCursor(Qt.PointingHandCursor)
        self.open_button.clicked.connect(self._submit)

        self.search_input = QLineEdit()
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(230)
        self.search_input.setMaximumWidth(320)
        self.search_input.textChanged.connect(self.search_changed)

        row.addWidget(self.url_input, 3)
        row.addWidget(self.open_button)
        row.addSpacing(12)
        row.addWidget(self.search_input, 1)
        outer.addLayout(row)

        self.feedback = QLabel("")
        self.feedback.hide()
        outer.addWidget(self.feedback)

        self._url_action = self.url_input.addAction(icon("link", tokens["text_secondary"], 18), QLineEdit.LeadingPosition)
        self._search_action = self.search_input.addAction(
            icon("search", tokens["text_secondary"], 18), QLineEdit.LeadingPosition
        )
        self.retranslate()

    def set_compact(self, compact):
        """Layout compacto: só o campo do link e o botão; a busca da biblioteca sai e as margens encolhem."""
        self._compact = compact
        self.search_input.setVisible(not compact)
        self.menu_button.setVisible(compact)
        self.url_input.setMinimumWidth(120 if compact else 280)
        self.layout().setContentsMargins(*((10, 8, 10, 6) if compact else (20, 12, 20, 8)))

    def focus_url(self):
        self.url_input.setFocus()
        self.url_input.selectAll()

    def focus_search(self):
        self.search_input.setFocus()
        self.search_input.selectAll()

    def set_tokens(self, tokens):
        self._tokens = tokens
        self.menu_button.setIcon(icon("panel", tokens["text_primary"], 20))
        self._url_action.setIcon(icon("link", tokens["text_secondary"], 18))
        self._search_action.setIcon(icon("search", tokens["text_secondary"], 18))

    def retranslate(self):
        t = self._tr.t
        self.url_input.setPlaceholderText(t("topbar.url_placeholder"))
        self.open_button.setText(t("topbar.open"))
        self.search_input.setPlaceholderText(t("topbar.search_placeholder"))
        self.menu_button.setToolTip(t("compact.menu"))
        self.menu_button.setAccessibleName(t("compact.menu"))
        self.url_input.setAccessibleName(t("topbar.url_placeholder"))
        self.search_input.setAccessibleName(t("topbar.search_placeholder"))
        for field in (self.url_input, self.search_input):
            for button in field.findChildren(QToolButton):  # botão 'limpar' nativo do campo
                button.setAccessibleName(t("topbar.clear"))
                button.setToolTip(t("topbar.clear"))
        self.show_message("")

    def show_message(self, text, error=False):
        self.feedback.setObjectName("statusError" if error else "statusOk")
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)
        self.feedback.setText(text)
        self.feedback.setVisible(bool(text))
        self.url_input.setProperty("invalid", error)
        self.url_input.style().unpolish(self.url_input)
        self.url_input.style().polish(self.url_input)

    def _clear_error(self):
        if self.url_input.property("invalid"):
            self.show_message("")

    def _submit(self):
        text = self.url_input.text().strip()
        if not text:
            return
        video_id = extract_video_id(text)
        if video_id is None:
            self.show_message(self._tr.t("topbar.invalid_url"), error=True)
            return
        self.show_message("")
        self.video_requested.emit(video_id)
