import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from app.domain.errors import StorageError
from app.services.storage_service import (
    FORMAT_JSON,
    FORMAT_SQLITE,
    FORMATS,
    MODE_DATABASE,
    MODE_FOLDER,
    STATUS_READY,
    SUBFOLDERS,
    format_bytes,
    suggested_root,
)


class StorageDialog(QDialog):
    """Escolha da pasta e do modo de armazenamento, no primeiro uso e ao trocar o local."""

    def __init__(self, translator, manager, first_run, parent=None):
        super().__init__(parent)
        self._tr = translator
        self._manager = manager
        self._first_run = first_run
        self.setModal(True)
        self.setFixedWidth(640)
        t = translator.t

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        # Largura fixa + altura calculada pelo layout: textos que quebram linha nunca são cortados
        layout.setSizeConstraint(QLayout.SetFixedSize)

        title = QLabel(t("storage.title"))
        title.setObjectName("pageTitle")
        subtitle = QLabel(t("storage.subtitle_first" if first_run else "storage.subtitle_change"))
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(6)

        layout.addWidget(self._field_label(t("storage.folder")))
        row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setAccessibleName(t("storage.folder"))
        self.browse_button = QPushButton(t("storage.browse"))
        self.browse_button.setObjectName("secondary")
        self.browse_button.setCursor(Qt.PointingHandCursor)
        self.browse_button.clicked.connect(self._browse)
        row.addWidget(self.path_input, 1)
        row.addWidget(self.browse_button)
        layout.addLayout(row)
        self.free_label = QLabel()
        self.free_label.setObjectName("pageSubtitle")
        layout.addWidget(self.free_label)

        self.mode_buttons = {}
        group = QButtonGroup(self)
        for mode in (MODE_FOLDER, MODE_DATABASE):
            card, radio = self._mode_card(mode, t(f"storage.mode_{mode}"), t(f"storage.mode_{mode}_desc"))
            group.addButton(radio)
            self.mode_buttons[mode] = radio
            layout.addWidget(card)

        self.format_row = QFrame()
        fmt_layout = QHBoxLayout(self.format_row)
        fmt_layout.setContentsMargins(0, 0, 0, 0)
        fmt_layout.addWidget(self._field_label(t("storage.format")))
        self.format_combo = QComboBox()
        self.format_combo.setAccessibleName(t("storage.format"))
        self.format_combo.addItem(t("storage.format_sqlite"), FORMAT_SQLITE)
        self.format_combo.addItem(t("storage.format_json"), FORMAT_JSON)
        fmt_layout.addWidget(self.format_combo)
        fmt_layout.addStretch(1)
        layout.addWidget(self.format_row)

        self.preview_label = QLabel(t("storage.preview", folders=", ".join(SUBFOLDERS)))
        self.preview_label.setObjectName("pageSubtitle")
        self.preview_label.setWordWrap(True)
        layout.addWidget(self.preview_label)

        self.migrate_check = QCheckBox()
        self._migrate_wanted = True  # escolha do usuário; só muda quando ele clica na caixa
        self.migrate_check.clicked.connect(lambda checked: setattr(self, "_migrate_wanted", checked))
        self.notice_label = QLabel()
        self.notice_label.setObjectName("pageSubtitle")
        self.notice_label.setWordWrap(True)
        layout.addWidget(self.migrate_check)
        layout.addWidget(self.notice_label)

        self.error_label = QLabel()
        self.error_label.setObjectName("statusError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.cancel_button = QPushButton(t("storage.quit" if first_run else "storage.cancel"))
        self.cancel_button.setObjectName("secondary")
        self.cancel_button.clicked.connect(self.reject)
        self.save_button = QPushButton(t("storage.save"))
        self.save_button.setObjectName("primary")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._save)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)

        self._prefill()
        self.path_input.textChanged.connect(self._refresh)
        for radio in self.mode_buttons.values():
            radio.toggled.connect(self._refresh)
        self.format_combo.currentIndexChanged.connect(self._refresh)
        self._refresh()

    # -- construção -----------------------------------------------------
    @staticmethod
    def _field_label(text):
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def _mode_card(self, mode, title, description):
        card = QFrame()
        card.setObjectName("card")
        box = QVBoxLayout(card)
        box.setContentsMargins(16, 12, 16, 12)
        box.setSpacing(4)
        radio = QRadioButton(title)
        radio.setAccessibleName(title)
        radio.setAccessibleDescription(description)
        radio.setCursor(Qt.PointingHandCursor)
        desc = QLabel(description)
        desc.setObjectName("pageSubtitle")
        desc.setWordWrap(True)
        desc.setContentsMargins(26, 0, 0, 0)
        box.addWidget(radio)
        box.addWidget(desc)
        return card, radio

    def _prefill(self):
        config = self._manager.config
        if config is not None:
            self.path_input.setText(str(config.root))
            self.mode_buttons[config.mode].setChecked(True)
            self.format_combo.setCurrentIndex(self.format_combo.findData(config.format))
        else:
            self.path_input.setText(str(suggested_root()))
            self.mode_buttons[MODE_FOLDER].setChecked(True)

    # -- leitura do estado -----------------------------------------------
    @property
    def mode(self):
        return MODE_DATABASE if self.mode_buttons[MODE_DATABASE].isChecked() else MODE_FOLDER

    @property
    def format(self):
        return self.format_combo.currentData() if self.mode == MODE_FOLDER else FORMAT_SQLITE

    # -- comportamento ---------------------------------------------------
    def _browse(self):
        start = self.path_input.text().strip() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, self._tr.t("storage.browse_title"), start)
        if chosen:
            self.path_input.setText(chosen)

    def _refresh(self, *_):
        self.format_row.setVisible(self.mode == MODE_FOLDER)
        self._hide_error()
        text = self.path_input.text().strip()
        self.free_label.setText("")
        folder = Path(text).expanduser() if text else None
        if folder is not None and folder.is_absolute():
            probe = folder
            while not probe.exists() and probe != probe.parent:
                probe = probe.parent
            try:
                usage = shutil.disk_usage(probe)
                self.free_label.setText(
                    self._tr.t("storage.free_space", free=format_bytes(usage.free), total=format_bytes(usage.total))
                )
            except OSError:
                pass

        can_migrate = False
        notice = ""
        if self._manager.status() == STATUS_READY and folder is not None and folder.is_absolute():
            try:
                plan = self._manager.plan(folder, self.mode, self.format)
            except StorageError:
                plan = None
            if plan is not None and not plan.same_location:
                if plan.target_has_data:
                    notice = self._tr.t("storage.target_has_data")
                elif plan.videos or plan.categories or plan.playlists:
                    can_migrate = True
                    self.migrate_check.setText(self._tr.t("storage.migrate", videos=plan.videos))
        self.migrate_check.setVisible(can_migrate)
        self.migrate_check.setChecked(can_migrate and self._migrate_wanted)
        self.notice_label.setText(notice)
        self.notice_label.setVisible(bool(notice))

    def _hide_error(self):
        self.error_label.hide()
        self.error_label.setText("")

    def _show_error(self, exc):
        key = f"error.{exc.code}"
        text = self._tr.t(key)
        if text == key:
            text = self._tr.t("error.unknown")
        self.error_label.setText(text)
        self.error_label.show()

    def _save(self):
        try:
            self._manager.configure(
                self.path_input.text(), self.mode, self.format, migrate=self.migrate_check.isChecked()
            )
        except StorageError as exc:
            self._show_error(exc)
            return
        self.accept()
