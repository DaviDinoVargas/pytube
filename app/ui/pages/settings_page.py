from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import LANGUAGES
from app.services.storage_service import STATUS_READY, STATUS_ROOT_MISSING, STATUS_UNCONFIGURED, format_bytes
from app.styles.tokens import THEME_CHOICES
from app.ui.pages.base import Page
from app.ui.widgets.theme_swatch import ThemeSwatch

SWATCH_COLUMNS = 3


class SettingsPage(Page):
    key = "settings"
    language_selected = Signal(str)
    theme_selected = Signal(str)
    change_storage_requested = Signal()
    open_storage_requested = Signal()

    def __init__(self, translator, language, theme, storage=None, settings=None):
        super().__init__(translator)
        self._storage = storage
        self._settings = settings
        self._sections = []
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
        self.restore_check = QCheckBox()
        self.restore_check.setVisible(settings is not None)
        if settings is not None:
            self.restore_check.setChecked(settings.restore_last_page)
            self.restore_check.toggled.connect(lambda v: setattr(settings, "restore_last_page", v))
        general.layout().addWidget(self.restore_check)

        appearance = self._card()
        appearance.layout().addWidget(self.theme_title)
        appearance.layout().addWidget(self.theme_hint)
        appearance.layout().addWidget(swatches)

        storage_card = self._build_storage_card()

        self.body.addWidget(general)
        self.body.addWidget(storage_card)
        self.body.addWidget(appearance)
        self.body.addStretch(1)
        self.retranslate()

    def _build_storage_card(self):
        card = self._card()
        self.storage_title = QLabel()
        self.storage_title.setObjectName("groupTitle")
        card.layout().addWidget(self.storage_title)
        form = QFormLayout()
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.storage_rows = {}
        for key in ("path", "mode", "format", "free", "library", "files"):
            name = QLabel()
            name.setObjectName("fieldLabel")
            value = QLabel()
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form.addRow(name, value)
            self.storage_rows[key] = (name, value)
        card.layout().addLayout(form)
        self.storage_warning = QLabel()
        self.storage_warning.setObjectName("statusError")
        self.storage_warning.setWordWrap(True)
        card.layout().addWidget(self.storage_warning)
        buttons = QHBoxLayout()
        self.open_folder_button = QPushButton()
        self.open_folder_button.setObjectName("secondary")
        self.open_folder_button.clicked.connect(self.open_storage_requested)
        self.change_storage_button = QPushButton()
        self.change_storage_button.setObjectName("secondary")
        self.change_storage_button.clicked.connect(self.change_storage_requested)
        for button in (self.open_folder_button, self.change_storage_button):
            button.setCursor(Qt.PointingHandCursor)
            buttons.addWidget(button)
        buttons.addStretch(1)
        card.layout().addLayout(buttons)
        return card

    def refresh_storage(self):
        """Atualiza o cartão de armazenamento com o estado atual do gerenciador."""
        if self._storage is None:
            return
        t = self._tr.t
        status = self._storage.status()
        values = {key: "—" for key in self.storage_rows}
        self.storage_warning.setText("")
        if status == STATUS_UNCONFIGURED:
            values["path"] = t("settings.storage_unset")
        else:
            cfg = self._storage.config
            values["path"] = str(cfg.root)
            values["mode"] = t(f"storage.mode_short_{cfg.mode}")
            values["format"] = t(f"storage.format_short_{cfg.format}") if cfg.mode == "folder" else t("storage.format_short_sqlite")
            if status == STATUS_ROOT_MISSING:
                self.storage_warning.setText(t("settings.storage_missing"))
            elif status == STATUS_READY:
                usage = self._storage.usage()
                counts = self._storage.store.counts()
                values["free"] = f"{format_bytes(usage['free'])} / {format_bytes(usage['total'])}"
                values["library"] = t(
                    "storage.library_summary", videos=counts["videos"], categories=counts["categories"], playlists=counts["playlists"]
                )
                values["files"] = t("storage.files_summary", count=usage["video_files"], size=format_bytes(usage["videos_bytes"]))
        for key, (_name, label) in self.storage_rows.items():
            label.setText(values[key])
        self.storage_warning.setVisible(bool(self.storage_warning.text()))
        self.open_folder_button.setEnabled(status == STATUS_READY)

    def add_section(self, card):
        """Acrescenta uma seção (cartão) antes do espaço final da página."""
        self._sections.append(card)
        self.body.insertWidget(self.body.count() - 1, card)

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
        self.language_combo.setAccessibleName(t("settings.language"))
        self.theme_title.setText(t("settings.theme").upper())
        self.theme_hint.setText(t("settings.theme_hint"))
        for name, swatch in self.theme_buttons.items():
            swatch.set_label(t(f"theme.{name}"))
        self.restore_check.setText(t("settings.restore_last_page"))
        for card in self._sections:
            card.retranslate()
        self.storage_title.setText(t("settings.group_storage").upper())
        for key, (name, _value) in self.storage_rows.items():
            name.setText(t(f"settings.storage_{key}"))
        self.open_folder_button.setText(t("settings.storage_open"))
        self.change_storage_button.setText(t("settings.storage_change"))
        self.refresh_storage()
