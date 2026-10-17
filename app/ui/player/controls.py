from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QSlider, QToolButton, QVBoxLayout

from app.domain import playback
from app.domain.states import format_duration
from app.styles.icons import icon

SEEK_RANGE = 1000


class ClickSlider(QSlider):
    """QSlider que salta para o ponto clicado (o padrão só anda em passos de página)."""

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            span = self.maximum() - self.minimum()
            fraction = event.position().x() / max(1, self.width())
            self.setValue(self.minimum() + round(span * max(0.0, min(1.0, fraction))))
            self.sliderMoved.emit(self.value())
        super().mousePressEvent(event)


def _speed_label(rate):
    return f"{rate:g}×"


class PlayerControls(QFrame):
    play_toggled = Signal()
    seek_requested = Signal(float)
    volume_changed = Signal(int)
    mute_toggled = Signal()
    rate_selected = Signal(float)
    quality_selected = Signal(object)  # altura (int) ou None para automática
    fullscreen_toggled = Signal()
    mini_toggled = Signal()

    def __init__(self, translator, tokens):
        super().__init__()
        self.setObjectName("playerControls")
        self._tr = translator
        self._tokens = tokens
        self._duration = 0.0
        self._playing = False
        self._muted = False
        self._volume = 80
        self._rate = 1.0
        self._fullscreen = False
        self._mini = False
        self._seeking = False
        self._current_height = 0
        self._available = []
        self._can_change_quality = False
        self._source = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 6, 12, 8)
        outer.setSpacing(2)

        self.seek_slider = ClickSlider(Qt.Horizontal)
        self.seek_slider.setObjectName("seekSlider")
        self.seek_slider.setRange(0, SEEK_RANGE)
        self.seek_slider.setFocusPolicy(Qt.NoFocus)
        self.seek_slider.sliderPressed.connect(lambda: setattr(self, "_seeking", True))
        self.seek_slider.sliderMoved.connect(self._preview_seek)
        self.seek_slider.sliderReleased.connect(self._commit_seek)
        outer.addWidget(self.seek_slider)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.play_button = self._button("play", self.play_toggled.emit)
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setObjectName("playerTime")
        row.addWidget(self.play_button)
        row.addWidget(self.time_label)
        row.addStretch(1)

        self.mute_button = self._button("volume", self.mute_toggled.emit)
        self.volume_slider = ClickSlider(Qt.Horizontal)
        self.volume_slider.setObjectName("volumeSlider")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self._volume)
        self.volume_slider.setFixedWidth(90)
        self.volume_slider.setFocusPolicy(Qt.NoFocus)
        self.volume_slider.valueChanged.connect(self._on_volume_slider)
        row.addWidget(self.mute_button)
        row.addWidget(self.volume_slider)

        self.speed_button = self._menu_button()
        self.quality_button = self._menu_button()
        self.source_chip = QLabel()
        self.source_chip.setObjectName("sourceChip")
        self.fullscreen_button = self._button("maximize", self.fullscreen_toggled.emit)
        self.mini_button = self._button("mini", self.mini_toggled.emit)
        row.addWidget(self.speed_button)
        row.addWidget(self.quality_button)
        row.addWidget(self.source_chip)
        row.addWidget(self.mini_button)
        row.addWidget(self.fullscreen_button)
        outer.addLayout(row)
        self.refresh()

    # -- construção -------------------------------------------------------------------
    def _button(self, icon_name, slot):
        button = QToolButton()
        button.setObjectName("playerButton")
        button.setIconSize(QSize(20, 20))
        button.setCursor(Qt.PointingHandCursor)
        button.setFocusPolicy(Qt.TabFocus)
        button.clicked.connect(slot)
        button.setProperty("iconName", icon_name)
        return button

    def _menu_button(self):
        button = QToolButton()
        button.setObjectName("playerMenuButton")
        button.setPopupMode(QToolButton.InstantPopup)
        button.setCursor(Qt.PointingHandCursor)
        button.setFocusPolicy(Qt.TabFocus)
        button.setMenu(QMenu(button))
        return button

    # -- estado vindo do player ------------------------------------------------------------
    def set_playing(self, playing):
        self._playing = playing
        self.refresh()

    def set_position(self, position, duration):
        self._duration = max(0.0, duration)
        if not self._seeking and self._duration > 0:
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(int(min(1.0, position / self._duration) * SEEK_RANGE))
            self.seek_slider.blockSignals(False)
        self.time_label.setText(f"{format_duration(position) or '0:00'} / {format_duration(duration) or '0:00'}")

    def set_status(self, volume, muted, rate):
        self._volume, self._muted, self._rate = volume, muted, rate
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(int(volume))
        self.volume_slider.blockSignals(False)
        self.refresh()

    def set_quality(self, current_height, available, can_change):
        self._current_height, self._available, self._can_change_quality = current_height, list(available), can_change
        self.refresh()

    def set_source(self, kind):
        self._source = kind or ""
        self.source_chip.setText(self._tr.t(f"player.source_{kind}") if kind else "")
        self.source_chip.setProperty("source", self._source)
        self.source_chip.style().unpolish(self.source_chip)
        self.source_chip.style().polish(self.source_chip)

    def set_fullscreen(self, fullscreen):
        self._fullscreen = fullscreen
        self.refresh()

    def set_mini(self, mini):
        """No mini player só ficam o essencial: tocar, tempo, mudo e voltar à página do vídeo."""
        self._mini = mini
        for widget in (self.volume_slider, self.speed_button, self.quality_button, self.source_chip, self.fullscreen_button):
            widget.setVisible(not mini)
        self.refresh()

    def reset(self):
        self._duration, self._playing, self._current_height, self._available = 0.0, False, 0, []
        self.seek_slider.setValue(0)
        self.time_label.setText("0:00 / 0:00")
        self.refresh()

    # -- eventos do usuário -------------------------------------------------------------------
    def _preview_seek(self, value):
        if self._duration > 0:
            self.time_label.setText(
                f"{format_duration(value / SEEK_RANGE * self._duration) or '0:00'} / {format_duration(self._duration) or '0:00'}"
            )

    def _commit_seek(self):
        self._seeking = False
        if self._duration > 0:
            self.seek_requested.emit(self.seek_slider.value() / SEEK_RANGE * self._duration)

    def _on_volume_slider(self, value):
        self._volume = value
        self.volume_changed.emit(value)
        self.refresh()

    # -- aparência ----------------------------------------------------------------------------
    def set_tokens(self, tokens):
        self._tokens = tokens
        self.refresh()

    def refresh(self):
        t = self._tr.t
        color = self._tokens["text_primary"]
        self.play_button.setIcon(icon("pause" if self._playing else "play", color))
        self._label(self.play_button, t("player.pause" if self._playing else "player.play"))
        silent = self._muted or self._volume == 0
        self.mute_button.setIcon(icon("volume_off" if silent else "volume", color))
        self._label(self.mute_button, t("player.unmute" if silent else "player.mute"))
        self.fullscreen_button.setIcon(icon("minimize" if self._fullscreen else "maximize", color))
        self._label(self.fullscreen_button, t("player.exit_fullscreen" if self._fullscreen else "player.fullscreen"))
        self.mini_button.setIcon(icon("mini", color))
        self._label(self.mini_button, t("player.mini_expand" if self._mini else "player.mini"))
        self._fill_speed_menu()
        self._fill_quality_menu()

    @staticmethod
    def _label(button, text):
        button.setToolTip(text)
        button.setAccessibleName(text)

    def _fill_speed_menu(self):
        self.speed_button.setText(_speed_label(self._rate))
        self._label(self.speed_button, self._tr.t("player.speed"))
        menu = self.speed_button.menu()
        menu.clear()
        for rate in playback.SPEEDS:
            action = menu.addAction(_speed_label(rate))
            action.setCheckable(True)
            action.setChecked(abs(rate - self._rate) < 1e-6)
            action.triggered.connect(lambda _=False, r=rate: self.rate_selected.emit(r))

    def _fill_quality_menu(self):
        t = self._tr.t
        current = f"{self._current_height}p" if self._current_height else t("player.auto")
        self.quality_button.setText(current)
        tip = t("player.quality_current", quality=current) if self._current_height else t("player.quality")
        self._label(self.quality_button, tip)
        self.quality_button.setEnabled(bool(self._current_height or self._available))
        menu = self.quality_button.menu()
        menu.clear()
        if self._can_change_quality:
            auto = menu.addAction(t("player.auto"))
            auto.triggered.connect(lambda _=False: self._choose_quality(None))
            for height in self._available:
                action = menu.addAction(f"{height}p")
                action.setCheckable(True)
                action.setChecked(height == self._current_height)
                action.triggered.connect(lambda _=False, h=height: self._choose_quality(h))
        elif self._current_height:
            action = menu.addAction(f"{self._current_height}p · {t('player.source_local')}")
            action.setEnabled(False)

    def _choose_quality(self, height):
        """Pede a troca e, em seguida, volta o menu ao que o player de fato reporta (a troca pode ser ignorada)."""
        self.quality_selected.emit(height)
        QTimer.singleShot(0, self.refresh)

    def retranslate(self):
        self.seek_slider.setAccessibleName(self._tr.t("player.seek"))
        self.volume_slider.setAccessibleName(self._tr.t("player.volume"))
        self.set_source(self._source)
        self.refresh()
