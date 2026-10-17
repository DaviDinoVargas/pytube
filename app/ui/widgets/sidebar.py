from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout

from app.styles.icons import icon

NAV_ITEMS = ("home", "continue", "library", "downloaded", "playlists", "categories", "history", "downloads")
EXPANDED_WIDTH = 232
COLLAPSED_WIDTH = 64


class Sidebar(QFrame):
    page_selected = Signal(str)
    collapsed_changed = Signal(bool)

    def __init__(self, translator, tokens, collapsed=False):
        super().__init__()
        self.setObjectName("sidebar")
        self._tr = translator
        self._tokens = tokens
        self._collapsed = collapsed
        self._buttons = {}
        self._badges = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setSpacing(4)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 10)
        self._toggle = QToolButton()
        self._toggle.setObjectName("iconButton")
        self._toggle.setIconSize(QSize(20, 20))
        self._toggle.setCursor(Qt.PointingHandCursor)
        self._toggle.clicked.connect(lambda: self.set_collapsed(not self._collapsed))
        self._brand = QLabel("DinoTube")
        self._brand.setObjectName("brand")
        head.addWidget(self._toggle)
        head.addWidget(self._brand, 1)
        layout.addLayout(head)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for key in NAV_ITEMS:
            btn = QToolButton()
            btn.setObjectName("navItem")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setIconSize(QSize(20, 20))
            btn.toggled.connect(lambda _c: self._refresh_icons())
            btn.clicked.connect(lambda _=False, k=key: self.page_selected.emit(k))
            self._group.addButton(btn)
            layout.addWidget(btn)
            self._buttons[key] = btn
        layout.addStretch(1)

        self.refresh()

    def select(self, key):
        """Destaca o item `key`; com uma chave desconhecida (ex.: configurações) limpa o destaque."""
        if key in self._buttons:
            self._buttons[key].setChecked(True)
            return
        self._group.setExclusive(False)
        for btn in self._buttons.values():
            btn.setChecked(False)
        self._group.setExclusive(True)

    def set_collapsed(self, collapsed):
        self._collapsed = collapsed
        self.refresh()
        self.collapsed_changed.emit(collapsed)

    @property
    def collapsed(self):
        return self._collapsed

    def set_badge(self, key, count):
        """Contador ao lado do item (ex.: downloads em andamento). Zero esconde o contador."""
        if self._badges.get(key, 0) != count:
            self._badges[key] = count
            self.refresh()

    def badge(self, key):
        return self._badges.get(key, 0)

    def set_tokens(self, tokens):
        self._tokens = tokens
        self.refresh()

    def refresh(self):
        """Reaplica textos, ícones e largura conforme idioma, tema e estado de recolhimento."""
        self.setFixedWidth(COLLAPSED_WIDTH if self._collapsed else EXPANDED_WIDTH)
        self._brand.setVisible(not self._collapsed)
        self._toggle.setIcon(icon("panel", self._tokens["text_secondary"]))
        self._toggle.setToolTip(self._tr.t("nav.expand" if self._collapsed else "nav.collapse"))
        self._toggle.setAccessibleName(self._toggle.toolTip())
        for key, btn in self._buttons.items():
            label = self._tr.t(f"nav.{key}")
            count = self._badges.get(key, 0)
            shown = f"{label} · {count}" if count else label
            btn.setToolTip(shown)
            btn.setAccessibleName(shown)
            if self._collapsed:
                btn.setText("")
                btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
                btn.setFixedWidth(COLLAPSED_WIDTH - 24)
            else:
                btn.setText("  " + shown)
                btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
                btn.setFixedWidth(EXPANDED_WIDTH - 24)
        self._refresh_icons()

    def _refresh_icons(self):
        for key, btn in self._buttons.items():
            color = self._tokens["text_primary"] if btn.isChecked() else self._tokens["text_secondary"]
            btn.setIcon(icon(key, color))
