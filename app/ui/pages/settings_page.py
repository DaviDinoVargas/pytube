from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QComboBox, QFormLayout, QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from app.i18n import LANGUAGES
from app.styles.tokens import THEME_CHOICES
from app.ui.pages.base import Page
from app.ui.widgets.theme_swatch import ThemeSwatch

SWATCH_COLUMNS = 3


class SettingsPage(Page):
    key = "settings"
    language_selected = Signal(str)
    theme_selected = Signal(str)

    def __init__(self, translator, language, theme):
        super().__init__(translator)
        self.group_title = QLabel()
        self.group_title.setObjectName("groupTitle")

        self.language_label = QLabel()
        self.language_label.setObjectName("fieldLabel")
        self.language_combo = QComboBox()
        self.language_combo.setMinimumWidth(240)
        for code, name in LANGUAGES.items():
            self.language_combo.addItem(name, code)
        self.language_combo.setCurrentIndex(self.language_combo.findData(language))
        self.language_combo.currentIndexChanged.connect(
            lambda _i: self.language_selected.emit(self.language_combo.currentData())
        )

        self.theme_title = QLabel()
        self.theme_title.setObjectName("groupTitle")
        self.theme_hint = QLabel()
        self.theme_hint.setObjectName("pageSubtitle")
        self.theme_hint.setWordWrap(True)

        self.theme_buttons = {}
        self._theme_group = QButtonGroup(self)
        self._theme_group.setExclusive(True)
        swatches = QWidget()
        grid = QGridLayout(swatches)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(14)
        for i, name in enumerate(THEME_CHOICES):
            swatch = ThemeSwatch(name, name, "#8B7CF6")
            swatch.clicked.connect(lambda _=False, n=name: self.theme_selected.emit(n))
            self._theme_group.addButton(swatch)
            self.theme_buttons[name] = swatch
            grid.addWidget(swatch, i // SWATCH_COLUMNS, i % SWATCH_COLUMNS)
        grid.setColumnStretch(SWATCH_COLUMNS, 1)
        self.set_theme(theme)

        general = self._card()
        general.layout().addWidget(self.group_title)
        form = QFormLayout()
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(14)
        form.setFieldGrowthPolicy(QFormLayout.FieldsStayAtSizeHint)
        form.addRow(self.language_label, self.language_combo)
        general.layout().addLayout(form)

        appearance = self._card()
        appearance.layout().addWidget(self.theme_title)
        appearance.layout().addWidget(self.theme_hint)
        appearance.layout().addWidget(swatches)

        self.body.addWidget(general)
        self.body.addWidget(appearance)
        self.body.addStretch(1)
        self.retranslate()

    @staticmethod
    def _card():
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(12)
        return card

    def set_theme(self, name):
        if name in self.theme_buttons:
            self.theme_buttons[name].setChecked(True)

    def set_tokens(self, tokens):
        for swatch in self.theme_buttons.values():
            swatch.set_ring_color(tokens["accent"])

    def retranslate(self):
        super().retranslate()
        if not hasattr(self, "theme_buttons"):
            return
        t = self._tr.t
        self.group_title.setText(t("settings.group_general").upper())
        self.language_label.setText(t("settings.language"))
        self.theme_title.setText(t("settings.theme").upper())
        self.theme_hint.setText(t("settings.theme_hint"))
        for name, swatch in self.theme_buttons.items():
            swatch.set_label(t(f"theme.{name}"))
