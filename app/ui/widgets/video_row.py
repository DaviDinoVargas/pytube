from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout

from app.domain import states
from app.domain.states import format_duration
from app.styles.icons import icon
from app.ui.widgets.video_card import ActionsMixin, cover_pixmap, format_added

ROW_THUMB = (112, 63)


class VideoRow(ActionsMixin, QFrame):
    """Um vídeo em linha (visualização em lista): miniatura pequena, dados, categorias, estado e menu."""

    open_requested = Signal(int)
    action_requested = Signal(int, str)
    selection_changed = Signal(int, bool)

    def __init__(self, translator, tokens, video, state, thumb_path=None, can_download=False, organize=None, categories=()):
        super().__init__()
        self.video, self.state = video, state
        self._tr, self._can_download, self._organize = translator, can_download, organize
        self._selectable = False
        t = translator.t
        self.setObjectName("videoRow")
        self.setProperty("state", state)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        state_text = t(f"card.state_{state}") if state != states.SAVED else ""
        self.setAccessibleName(f"{video.title}. {state_text}".strip(". "))
        self.setToolTip(video.title)

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 6, 8)
        row.setSpacing(12)
        self.check = QCheckBox()
        self.check.setObjectName("cardCheck")
        self.check.setAccessibleName(t("card.select"))
        self.check.setFocusPolicy(Qt.NoFocus)
        self.check.toggled.connect(lambda checked: self.selection_changed.emit(self.video.id, checked))
        self.check.hide()
        row.addWidget(self.check)

        thumb = QLabel()
        thumb.setFixedSize(*ROW_THUMB)
        thumb.setPixmap(cover_pixmap(thumb_path, ROW_THUMB[0], ROW_THUMB[1], 8, tokens))
        row.addWidget(thumb)

        column = QVBoxLayout()
        column.setSpacing(2)
        self.title_label = QLabel(video.title or video.url)
        self.title_label.setObjectName("cardTitle")
        meta = [p for p in (video.channel, format_duration(video.duration), format_added(video.added_at, translator.language)) if p]
        self.meta_label = QLabel(" · ".join(meta))
        self.meta_label.setObjectName("cardMeta")
        column.addWidget(self.title_label)
        column.addWidget(self.meta_label)
        self.chips = []
        if categories:
            chip_row = QHBoxLayout()
            chip_row.setSpacing(6)
            for name, color in categories[:4]:
                chip = QLabel(("● " if color else "") + name)
                chip.setObjectName("categoryChip")
                if color:
                    chip.setStyleSheet(f"QLabel#categoryChip {{ border-color: {color}; }}")
                chip_row.addWidget(chip)
                self.chips.append(chip)
            chip_row.addStretch(1)
            column.addLayout(chip_row)
        row.addLayout(column, 1)

        self.state_label = QLabel(state_text)
        self.state_label.setObjectName("rowState")
        self.state_label.setProperty("state", state)
        self.state_label.setVisible(bool(state_text))
        row.addWidget(self.state_label)

        self.menu_button = QToolButton()
        self.menu_button.setObjectName("iconButton")
        self.menu_button.setIcon(icon("more", tokens["text_secondary"]))
        self.menu_button.setIconSize(QSize(20, 20))
        self.menu_button.setToolTip(t("card.more"))
        self.menu_button.setAccessibleName(t("card.more"))
        self.menu_button.setCursor(Qt.PointingHandCursor)
        self.menu_button.setPopupMode(QToolButton.InstantPopup)
        self.menu_button.setMenu(self._build_menu())
        row.addWidget(self.menu_button)

    # -- seleção e interação (igual ao card) -------------------------------------------
    def set_selectable(self, selectable):
        self._selectable = selectable
        self.check.setVisible(selectable)
        if not selectable:
            self.check.setChecked(False)

    @property
    def selected(self):
        return self.check.isChecked()

    def set_selected(self, selected):
        self.check.setChecked(selected)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.check.toggle() if self._selectable else self.open_requested.emit(self.video.id)
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        self._build_menu().exec(event.globalPos())

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.check.toggle() if self._selectable else self.open_requested.emit(self.video.id)
            return
        super().keyPressEvent(event)
