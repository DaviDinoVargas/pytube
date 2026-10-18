from datetime import datetime

from PySide6.QtCore import QLocale, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QMenu, QProgressBar, QToolButton, QVBoxLayout, QWidget

from app.domain import states
from app.domain.states import format_duration
from app.styles.icons import icon

CARD_W = 272
BORDER = 2  # borda sempre de 2 px: o destaque do estado não muda o tamanho do card
THUMB_W = CARD_W - 2 * BORDER
THUMB_H = 153  # ~16:9
RADIUS = 12

_BADGE_ICON = {
    states.DOWNLOADED: "check",
    states.MISSING: "warning",
    states.INVALID: "warning",
    states.FAILED: "warning",
    states.DOWNLOADING: "downloads",
}


def format_added(iso, language):
    try:
        date = datetime.fromisoformat(iso).astimezone().date()
    except (TypeError, ValueError):
        return ""
    locale = QLocale("pt_BR" if language == "pt-BR" else "en_US")
    return locale.toString(date, QLocale.ShortFormat)


def theme_radius(radius, tokens):
    """Raio dos cantos da miniatura acompanhando o tema: reto nos temas de fio, curto nos de borda dura."""
    style = tokens.get("card", "outline")
    if style == "line":
        return 0
    base = tokens["radius"]["md"]
    return round(radius * (min(base, 6) if style == "hard" else base) / 12)


def cover_pixmap(path, width, height, radius, tokens):
    """Miniatura recortada para preencher o espaço, com os cantos de cima arredondados."""
    radius = theme_radius(radius, tokens)
    out = QPixmap(width, height)
    out.fill(Qt.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, width, height + radius), radius, radius)
    painter.setClipPath(clip)
    source = QPixmap(str(path)) if path else QPixmap()
    if source.isNull():
        grad = QLinearGradient(QPointF(0, 0), QPointF(width, height))
        grad.setColorAt(0, QColor(tokens["surface_elevated"]))
        grad.setColorAt(1, QColor(tokens["background"]) if tokens["background"].startswith("#") else QColor(tokens["surface"]))
        painter.fillRect(0, 0, width, height, grad)
        play = icon("play", tokens["text_secondary"], 40).pixmap(40, 40)
        painter.drawPixmap((width - 40) // 2, (height - 40) // 2, play)
    else:
        scaled = source.scaled(width, height, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        painter.drawPixmap((width - scaled.width()) // 2, (height - scaled.height()) // 2, scaled)
    painter.end()
    return out


def _badge_text_color(state, tokens):
    """Cor do ícone do selo: a mesma do texto do selo no QSS (contrasta com a cor do estado)."""
    if state == states.DOWNLOADED:
        return tokens["text_on_downloaded"]
    return tokens["text_on_error"] if state == states.FAILED else tokens["text_on_warning"]


class StateBadge(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("stateBadge")
        row = QHBoxLayout(self)
        row.setContentsMargins(7, 3, 9, 3)
        row.setSpacing(4)
        self.icon_label = QLabel()
        self.text_label = QLabel()
        row.addWidget(self.icon_label)
        row.addWidget(self.text_label)
        self.hide()


class ActionsMixin:
    """Menu de ações compartilhado por cards e linhas de lista. Exige: video, state, _tr, _can_download, _organize
    e os sinais open_requested / action_requested."""

    def _build_menu(self):
        menu = QMenu(self)
        self._fill_menu(menu)
        menu.aboutToShow.connect(lambda m=menu: self._fill_menu(m))  # categorias e playlists sempre atuais ao abrir
        return menu

    def _fill_menu(self, menu):
        menu.clear()
        t = self._tr.t
        entries = [("open", t("card.menu_open"))]
        if self._can_download and self.state in (states.SAVED, states.MISSING, states.INVALID, states.FAILED):
            entries.append(("download", t("card.menu_download")))
        entries.append(("browser", t("card.menu_browser")))
        entries.append(("queue_add", t("queue.add")))
        entries.append(("queue_next", t("queue.play_next")))
        if self.state == states.DOWNLOADED:
            entries.append(("folder", t("card.menu_folder")))
        base_entries = list(entries)
        for key, label in entries:
            action = menu.addAction(label)
            action.triggered.connect(lambda _=False, k=key: self._emit_action(k))
        watch = getattr(self, "watch", "none")
        if watch == "watched":
            entries.append(("unwatch", t("card.menu_unwatched")))
        else:
            entries.append(("watch", t("card.menu_watched")))
        if watch != "none":
            entries.append(("restart", t("card.menu_restart")))
        if getattr(self, "_can_forget", False):
            entries.append(("forget", t("card.menu_forget")))
        for key, label in entries[len(base_entries):]:
            action = menu.addAction(label)
            action.triggered.connect(lambda _=False, k=key: self._emit_action(k))
        if self._organize is not None:
            menu.addMenu(self._organize.categories_menu([self.video.id], menu))
            menu.addMenu(self._organize.playlists_menu([self.video.id], menu))
        remove = menu.addAction(t("card.menu_remove"))
        remove.triggered.connect(lambda _=False: self._emit_action("remove"))

    def _emit_action(self, key):
        if key == "open":
            self.open_requested.emit(self.video.id)
        else:
            self.action_requested.emit(self.video.id, key)

    def action_keys(self):
        return [a.text() for a in self.menu_button.menu().actions()]



class VideoCard(ActionsMixin, QFrame):
    open_requested = Signal(int)
    action_requested = Signal(int, str)
    selection_changed = Signal(int, bool)

    def __init__(self, translator, tokens, video, state, thumb_path=None, can_download=False, organize=None, watch="none", fraction=0.0, can_forget=False):
        super().__init__()
        self.video = video
        self.state = state
        self.watch = watch
        self._can_forget = can_forget
        self._tr = translator
        self._can_download = can_download
        self._organize = organize
        self._selectable = False
        t = translator.t
        self.setObjectName("videoCard")
        self.setProperty("state", state)
        self.setFixedWidth(CARD_W)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(video.title)

        state_text = t(f"card.state_{state}") if state != states.SAVED else ""
        self.setAccessibleName(f"{video.title}. {state_text}".strip(". "))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(BORDER, BORDER, BORDER, BORDER)
        layout.setSpacing(0)

        thumb = QLabel()
        thumb.setFixedSize(THUMB_W, THUMB_H)
        thumb.setPixmap(cover_pixmap(thumb_path, THUMB_W, THUMB_H, RADIUS - BORDER, tokens))
        layout.addWidget(thumb)
        self.thumb = thumb

        self.duration_badge = None
        duration = format_duration(video.duration)
        if duration:
            self.duration_badge = QLabel(duration, thumb)
            self.duration_badge.setObjectName("badge")
            self.duration_badge.adjustSize()
            self.duration_badge.move(THUMB_W - self.duration_badge.width() - 8, THUMB_H - self.duration_badge.height() - 8)

        self.state_badge = None
        if state != states.SAVED:
            badge = StateBadge(thumb)
            badge.setProperty("state", state)
            badge.icon_label.setPixmap(
                icon(_BADGE_ICON[state], _badge_text_color(state, tokens), 14).pixmap(14, 14)
            )
            badge.text_label.setText(state_text)
            badge.adjustSize()
            badge.move(8, 8)
            badge.show()
            self.state_badge = badge

        self.progress_bar = QProgressBar(thumb)
        self.progress_bar.setObjectName("cardProgress")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(int(fraction * 1000))
        self.progress_bar.setProperty("watched", watch == "watched")
        self.progress_bar.setGeometry(0, THUMB_H - 4, THUMB_W, 4)
        self.progress_bar.setVisible(fraction > 0)
        if watch == "watched":
            self.setAccessibleName(f"{self.accessibleName()}. {translator.t('card.watched')}")
        elif fraction > 0:
            self.setAccessibleName(f"{self.accessibleName()}. {translator.t('card.progress', percent=int(fraction * 100))}")

        self.check = QCheckBox(thumb)
        self.check.setObjectName("cardCheck")
        self.check.setToolTip(translator.t("card.select"))
        self.check.setAccessibleName(translator.t("card.select"))
        self.check.move(THUMB_W - 34, 8)
        self.check.setFocusPolicy(Qt.NoFocus)
        self.check.toggled.connect(lambda checked: self.selection_changed.emit(self.video.id, checked))
        self.check.hide()

        info = QWidget()
        info_row = QHBoxLayout(info)
        info_row.setContentsMargins(12, 10, 6, 12)
        info_row.setSpacing(4)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.title_label = QLabel()
        self.title_label.setObjectName("cardTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        meta = QLabel(video.channel)
        meta.setObjectName("cardMeta")
        added = format_added(video.added_at, translator.language)
        added_label = QLabel(t("card.added", date=added) if added else "")
        added_label.setObjectName("cardMeta")
        texts.addWidget(self.title_label)
        texts.addWidget(meta)
        texts.addWidget(added_label)
        info_row.addLayout(texts, 1)

        self.menu_button = QToolButton()
        self.menu_button.setObjectName("iconButton")
        self.menu_button.setIcon(icon("more", tokens["text_secondary"]))
        self.menu_button.setToolTip(t("card.more"))
        self.menu_button.setAccessibleName(t("card.more"))
        self.menu_button.setCursor(Qt.PointingHandCursor)
        self.menu_button.setPopupMode(QToolButton.InstantPopup)
        self.menu_button.setMenu(self._build_menu())
        info_row.addWidget(self.menu_button, 0, Qt.AlignTop)
        layout.addWidget(info)
        self._finalize()

    def _finalize(self):
        """Aplica os estilos antes de medir: sem isso a altura sai calculada com a fonte padrão e o card é cortado."""
        self.ensurePolished()
        for child in self.findChildren(QWidget):
            child.ensurePolished()
        fm = QFontMetrics(self.title_label.font())
        self.title_label.setFixedHeight(fm.lineSpacing() * 2 + 4)
        self.title_label.setText(fm.elidedText(self.video.title or self.video.url, Qt.ElideRight, (CARD_W - 60) * 2 - 16))
        self.layout().activate()
        self.setFixedHeight(self.layout().sizeHint().height())

    # -- seleção ------------------------------------------------------------------
    def set_selectable(self, selectable):
        """No modo de seleção, clicar marca o card em vez de abri-lo."""
        self._selectable = selectable
        self.check.setVisible(selectable)
        if not selectable:
            self.check.setChecked(False)

    @property
    def selected(self):
        return self.check.isChecked()

    def set_selected(self, selected):
        self.check.setChecked(selected)

    # -- interação ----------------------------------------------------------------
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            if self._selectable:
                self.check.toggle()
            else:
                self.open_requested.emit(self.video.id)
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        self._build_menu().exec(event.globalPos())

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            if self._selectable:
                self.check.toggle()
            else:
                self.open_requested.emit(self.video.id)
            return
        super().keyPressEvent(event)
