from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from app.domain import playback
from app.services.provider_service import PACKAGES, can_self_update, installed_versions


class SettingsCard(QFrame):
    """Cartão de uma seção de configurações: título e linhas de formulário. As subclasses preenchem `self.form`."""

    title_key = ""

    def __init__(self, translator):
        super().__init__()
        self.setObjectName("card")
        self._tr = translator
        self.column = QVBoxLayout(self)
        self.column.setContentsMargins(20, 16, 20, 18)
        self.column.setSpacing(10)
        self.title_label = QLabel()
        self.title_label.setObjectName("groupTitle")
        self.column.addWidget(self.title_label)
        self.form = QFormLayout()
        self.form.setHorizontalSpacing(24)
        self.form.setVerticalSpacing(12)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldsStayAtSizeHint)
        self.column.addLayout(self.form)

    def row(self, label_text_key, widget):
        label = QLabel()
        label.setObjectName("fieldLabel")
        label.setProperty("key", label_text_key)
        self.form.addRow(label, widget)
        return label

    def retranslate(self):
        t = self._tr.t
        self.title_label.setText(t(self.title_key).upper())
        for i in range(self.form.rowCount()):
            item = self.form.itemAt(i, QFormLayout.LabelRole)
            if item is not None and item.widget() is not None and item.widget().property("key"):
                item.widget().setText(t(item.widget().property("key")))


class PlaybackCard(SettingsCard):
    """Volume inicial, velocidade padrão, retomar de onde parou e próximo da playlist."""

    title_key = "settings.group_playback"

    def __init__(self, translator, settings):
        super().__init__(translator)
        self._settings = settings
        volume_row = QHBoxLayout()
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(settings.player_volume)
        self.volume_slider.setFixedWidth(200)
        self.volume_value = QLabel(f"{settings.player_volume}%")
        self.volume_slider.valueChanged.connect(self._volume)
        volume_row.addWidget(self.volume_slider)
        volume_row.addWidget(self.volume_value)
        volume_row.addStretch(1)
        self.volume_label = self.row("settings.volume", volume_row)

        self.rate_combo = QComboBox()
        for rate in playback.SPEEDS:
            self.rate_combo.addItem(f"{rate:g}×", rate)
        self.rate_combo.setCurrentIndex(max(0, self.rate_combo.findData(settings.default_rate)))
        self.rate_combo.activated.connect(lambda _i: setattr(settings, "default_rate", self.rate_combo.currentData()))
        self.row("settings.default_rate", self.rate_combo)

        self.resume_check = QCheckBox()
        self.resume_check.setChecked(settings.resume_enabled)
        self.resume_check.toggled.connect(lambda v: setattr(settings, "resume_enabled", v))
        self.autoplay_check = QCheckBox()
        self.autoplay_check.setChecked(settings.autoplay_next)
        self.autoplay_check.toggled.connect(lambda v: setattr(settings, "autoplay_next", v))
        self.column.addWidget(self.resume_check)
        self.column.addWidget(self.autoplay_check)
        self.retranslate()

    def _volume(self, value):
        self._settings.player_volume = value
        self.volume_value.setText(f"{value}%")

    def retranslate(self):
        super().retranslate()
        if hasattr(self, "resume_check"):
            self.resume_check.setText(self._tr.t("settings.resume"))
            self.autoplay_check.setText(self._tr.t("settings.autoplay_next"))


class DownloadsCard(SettingsCard):
    title_key = "settings.group_downloads"
    concurrency_changed = Signal(int)
    ffmpeg_path_changed = Signal(str)  # '' = usar o ffmpeg do aplicativo
    ffmpeg_browse_requested = Signal()

    def __init__(self, translator, settings):
        super().__init__(translator)
        self._settings = settings
        self.concurrent_combo = QComboBox()
        for n in (1, 2, 3, 4):
            self.concurrent_combo.addItem(str(n), n)
        self.concurrent_combo.setCurrentIndex(max(0, self.concurrent_combo.findData(settings.download_concurrent)))
        self.concurrent_combo.activated.connect(self._concurrency)
        self.row("settings.concurrent", self.concurrent_combo)
        self.ffmpeg_label = QLabel()
        self.ffmpeg_label.setWordWrap(True)
        self.ffmpeg_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.row("settings.ffmpeg", self.ffmpeg_label)
        buttons = QHBoxLayout()
        self.browse_button = QPushButton()
        self.browse_button.setObjectName("secondary")
        self.browse_button.clicked.connect(self.ffmpeg_browse_requested)
        self.default_button = QPushButton()
        self.default_button.setObjectName("secondary")
        self.default_button.clicked.connect(lambda: self.ffmpeg_path_changed.emit(""))
        for b in (self.browse_button, self.default_button):
            b.setCursor(Qt.PointingHandCursor)
            buttons.addWidget(b)
        buttons.addStretch(1)
        self.column.addLayout(buttons)
        self._status = ("", False)
        self.retranslate()

    def _concurrency(self, _index):
        value = self.concurrent_combo.currentData()
        self._settings.download_concurrent = value
        self.concurrency_changed.emit(value)

    def set_ffmpeg_status(self, text, ok=True):
        self._status = (text, ok)
        self.ffmpeg_label.setText(text)
        self.ffmpeg_label.setObjectName("statusOk" if ok else "statusError")
        self.ffmpeg_label.style().unpolish(self.ffmpeg_label)
        self.ffmpeg_label.style().polish(self.ffmpeg_label)

    def retranslate(self):
        super().retranslate()
        if hasattr(self, "browse_button"):
            self.browse_button.setText(self._tr.t("settings.ffmpeg_choose"))
            self.default_button.setText(self._tr.t("settings.ffmpeg_default"))


class ProvidersCard(SettingsCard):
    title_key = "settings.group_providers"
    order_changed = Signal(tuple)
    update_requested = Signal()

    def __init__(self, translator, settings):
        super().__init__(translator)
        self._settings = settings
        self.order_combo = QComboBox()
        self.order_combo.activated.connect(self._order)
        self.row("settings.provider_order", self.order_combo)
        self.versions_label = QLabel()
        self.versions_label.setWordWrap(True)
        self.row("settings.provider_versions", self.versions_label)
        buttons = QHBoxLayout()
        self.update_button = QPushButton()
        self.update_button.setObjectName("secondary")
        self.update_button.setCursor(Qt.PointingHandCursor)
        self.update_button.clicked.connect(self.update_requested)
        buttons.addWidget(self.update_button)
        buttons.addStretch(1)
        self.column.addLayout(buttons)
        self.result_label = QLabel()
        self.result_label.setWordWrap(True)
        self.result_label.hide()
        self.column.addWidget(self.result_label)
        self.retranslate()

    def _order(self, _index):
        order = tuple(self.order_combo.currentData())
        self._settings.provider_order = order
        self.order_changed.emit(order)

    def refresh_versions(self):
        versions = installed_versions()
        parts = [f"{PACKAGES[name]} {version or '—'}" for name, version in versions.items()]
        self.versions_label.setText(" · ".join(parts))

    def set_busy(self, busy):
        self.update_button.setEnabled(not busy)
        if busy:
            self.show_result(self._tr.t("settings.provider_updating"), None)

    def show_result(self, text, ok):
        self.result_label.setText(text)
        self.result_label.setObjectName({True: "statusOk", False: "statusError", None: "cardMeta"}[ok])
        self.result_label.style().unpolish(self.result_label)
        self.result_label.style().polish(self.result_label)
        self.result_label.setVisible(bool(text))

    def retranslate(self):
        super().retranslate()
        if not hasattr(self, "order_combo"):
            return
        t = self._tr.t
        current = tuple(self._settings.provider_order)
        self.order_combo.clear()
        self.order_combo.addItem(t("settings.order_pytubefix_first"), ("pytubefix", "ytdlp"))
        self.order_combo.addItem(t("settings.order_ytdlp_first"), ("ytdlp", "pytubefix"))
        self.order_combo.setCurrentIndex(0 if current[:1] != ("ytdlp",) else 1)
        self.update_button.setText(t("settings.provider_update"))
        self.update_button.setToolTip("" if can_self_update() else t("settings.provider_update_frozen"))
        self.refresh_versions()


class MaintenanceCard(SettingsCard):
    title_key = "settings.group_maintenance"
    manage_space_requested = Signal()
    backups_requested = Signal()
    verify_requested = Signal()
    refresh_requested = Signal()
    clear_thumbs_requested = Signal()
    diagnostics_requested = Signal()
    logs_requested = Signal()

    ACTIONS = (
        ("manage_space", "settings.manage_space"), ("backups", "settings.backups"), ("verify", "settings.verify"),
        ("refresh", "settings.refresh_metadata"), ("clear_thumbs", "settings.clear_thumbs"),
        ("diagnostics", "settings.diagnostics"), ("logs", "settings.open_logs"),
    )

    def __init__(self, translator):
        super().__init__(translator)
        self.buttons = {}
        grid = QVBoxLayout()
        grid.setSpacing(6)
        for key, _text in self.ACTIONS:
            button = QPushButton()
            button.setObjectName("secondary")
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(getattr(self, f"{key}_requested").emit)
            grid.addWidget(button, 0, Qt.AlignLeft)
            self.buttons[key] = button
        self.column.addLayout(grid)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.hide()
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        self.column.addWidget(self.progress)
        self.column.addWidget(self.status_label)
        self.retranslate()

    def show_status(self, text, ok=True):
        self.status_label.setText(text)
        self.status_label.setObjectName("statusOk" if ok else "statusError")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.status_label.setVisible(bool(text))

    def show_progress(self, done, total):
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(done)
        self.progress.setVisible(done < total)

    def retranslate(self):
        super().retranslate()
        if hasattr(self, "buttons"):
            for key, text_key in self.ACTIONS:
                self.buttons[key].setText(self._tr.t(text_key))
