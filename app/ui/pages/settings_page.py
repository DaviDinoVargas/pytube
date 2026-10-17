from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QFormLayout, QFrame, QLabel, QVBoxLayout

from app.i18n import LANGUAGES
from app.services.settings_service import THEMES
from app.ui.pages.base import Page


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

        self.theme_label = QLabel()
        self.theme_label.setObjectName("fieldLabel")
        self.theme_combo = QComboBox()
        self.theme_combo.setMinimumWidth(240)
        for name in THEMES:
            self.theme_combo.addItem("", name)
        self.theme_combo.setCurrentIndex(self.theme_combo.findData(theme))
        self.theme_combo.currentIndexChanged.connect(
            lambda _i: self.theme_selected.emit(self.theme_combo.currentData())
        )

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 20)
        card_layout.setSpacing(12)
        card_layout.addWidget(self.group_title)
        form = QFormLayout()
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(14)
        form.setFieldGrowthPolicy(QFormLayout.FieldsStayAtSizeHint)
        form.addRow(self.language_label, self.language_combo)
        form.addRow(self.theme_label, self.theme_combo)
        card_layout.addLayout(form)

        self.body.addWidget(card)
        self.body.addStretch(1)
        self.retranslate()

    def retranslate(self):
        super().retranslate()
        if not hasattr(self, "theme_combo"):
            return
        t = self._tr.t
        self.group_title.setText(t("settings.group_general").upper())
        self.language_label.setText(t("settings.language"))
        self.theme_label.setText(t("settings.theme"))
        for i, name in enumerate(THEMES):
            self.theme_combo.setItemText(i, t(f"theme.{name}"))
