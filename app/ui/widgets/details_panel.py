from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFormLayout, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu, QPlainTextEdit, QPushButton, QToolButton,
    QVBoxLayout, QWidget,
)

from app.domain import states
from app.domain.notes import parse_markers
from app.domain.states import format_duration, video_state
from app.services.library_service import NOTES_LIMIT
from app.services.storage_service import format_bytes
from app.ui.widgets.video_card import cover_pixmap, format_added

SAVE_DELAY_MS = 700
PANEL_WIDTH = 290


class DetailsPanel(QFrame):
    """Metadados, categorias e anotações do vídeo aberto. As anotações são gravadas sozinhas, pouco depois de parar de digitar,
    sempre no vídeo certo (mesmo se você trocar de vídeo logo em seguida)."""

    timestamp_requested = Signal()  # pede o tempo atual do player para inserir nas notas
    seek_requested = Signal(float)  # clique num marcador: leva o player até aquele ponto
    folder_requested = Signal()

    def __init__(self, translator, library, organize=None, with_player=True, tokens=None):
        super().__init__()
        self.setObjectName("detailsPanel")
        self._with_player = with_player  # sem player ao lado (prévia do Gerenciador), não há "tempo atual" para inserir
        self._tokens = tokens
        self.setMinimumWidth(PANEL_WIDTH - 40)
        self._tr = translator
        self._library = library
        self._organize = organize
        self._video = None
        self._loading = False
        self._dirty = False

        column = QVBoxLayout(self)
        column.setContentsMargins(16, 14, 16, 14)
        column.setSpacing(10)
        self.thumb = QLabel()  # miniatura: só a prévia do Gerenciador a usa
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.hide()
        column.addWidget(self.thumb)
        self.heading = QLabel()
        self.heading.setObjectName("groupTitle")
        column.addWidget(self.heading)
        self.name_label = QLabel()
        self.name_label.setObjectName("cardTitle")
        self.name_label.setWordWrap(True)
        column.addWidget(self.name_label)

        self.form = QFormLayout()
        self.form.setHorizontalSpacing(12)
        self.form.setVerticalSpacing(6)
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self._rows = {}
        for key in ("channel", "duration", "added", "state", "file"):
            label = QLabel()
            label.setObjectName("cardMeta")
            value = QLabel()
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.form.addRow(label, value)
            self._rows[key] = (label, value)
        column.addLayout(self.form)
        self.folder_button = QPushButton()
        self.folder_button.setObjectName("linkButton")
        self.folder_button.setCursor(Qt.PointingHandCursor)
        self.folder_button.clicked.connect(self.folder_requested)
        column.addWidget(self.folder_button, 0, Qt.AlignLeft)

        self.categories_title = QLabel()
        self.categories_title.setObjectName("groupTitle")
        column.addWidget(self.categories_title)
        self.categories_label = QLabel()
        self.categories_label.setWordWrap(True)
        self.categories_menu_button = QToolButton()
        self.categories_menu_button.setObjectName("playerMenuButton")
        self.categories_menu_button.setPopupMode(QToolButton.InstantPopup)
        self.categories_menu_button.setCursor(Qt.PointingHandCursor)
        menu = QMenu(self.categories_menu_button)
        menu.aboutToShow.connect(lambda m=menu: self._fill_categories_menu(m))
        self.categories_menu_button.setMenu(menu)
        cats = QHBoxLayout()
        cats.addWidget(self.categories_label, 1)
        cats.addWidget(self.categories_menu_button, 0, Qt.AlignTop)
        column.addLayout(cats)

        notes_head = QHBoxLayout()
        self.notes_title = QLabel()
        self.notes_title.setObjectName("groupTitle")
        self.timestamp_button = QPushButton()
        self.timestamp_button.setObjectName("linkButton")
        self.timestamp_button.setCursor(Qt.PointingHandCursor)
        self.timestamp_button.clicked.connect(self.timestamp_requested)
        notes_head.addWidget(self.notes_title)
        notes_head.addStretch(1)
        notes_head.addWidget(self.timestamp_button)
        column.addLayout(notes_head)
        self.notes = QPlainTextEdit()
        self.notes.setObjectName("notesEdit")
        self.notes.setMinimumHeight(140)
        self.notes.textChanged.connect(self._on_text_changed)
        column.addWidget(self.notes, 1)
        self.status_label = QLabel()
        self.status_label.setObjectName("cardMeta")
        column.addWidget(self.status_label)
        self.markers_title = QLabel()
        self.markers_title.setObjectName("groupTitle")
        self.markers = QListWidget()
        self.markers.setObjectName("markersList")
        self.markers.setFrameShape(QFrame.NoFrame)
        self.markers.setMaximumHeight(130)
        self.markers.itemClicked.connect(self._marker_clicked)
        self.markers.itemActivated.connect(self._marker_clicked)
        self.markers_hint = QLabel()
        self.markers_hint.setObjectName("cardMeta")
        self.markers_hint.setWordWrap(True)
        for widget in (self.markers_title, self.markers, self.markers_hint):
            widget.setVisible(with_player)
            column.addWidget(widget)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(SAVE_DELAY_MS)
        self._timer.timeout.connect(self.flush)
        library.changed.connect(self._on_library_changed)
        self.retranslate()
        self.set_video(None)

    # -- dados -----------------------------------------------------------------------------
    @property
    def video(self):
        return self._video

    def set_video(self, video):
        """Mostra o vídeo (ou nada, se `video` é None ou ainda não está na biblioteca). Grava antes as notas pendentes."""
        self.flush()
        if video is not None and video.id is not None:
            video = self._library.get(video.id) or video  # dados atuais (a cópia do chamador pode ter notas antigas)
        self._video = video if video is not None and video.id is not None else None
        self._fill()

    def _fill(self):
        t = self._tr.t
        video = self._video
        saved = video is not None
        self._loading = True
        self.name_label.setText(video.title if saved else t("details.none"))
        values = dict.fromkeys(self._rows, "—")
        if saved:
            values["channel"] = video.channel or "—"
            values["duration"] = format_duration(video.duration) or "—"
            values["added"] = format_added(video.added_at, self._tr.language) or "—"
            state = video_state(video)
            values["state"] = t(f"card.state_{state}") if state != states.SAVED else t("details.state_saved")
            if state == states.DOWNLOADED:
                values["state"] = f"{t('card.state_downloaded')} · {video.local_quality or '—'} · {format_bytes(video.local_size or 0)}"
            path = self._library.local_path(video) if state == states.DOWNLOADED else None
            values["file"] = str(path) if path is not None else "—"
        for key, (_label, value) in self._rows.items():
            value.setText(values[key])
        self.folder_button.setVisible(saved and values["file"] != "—")
        self.categories_label.setText(self._categories_text())
        self.categories_menu_button.setEnabled(saved and self._organize is not None)
        self.notes.setPlainText(video.notes if saved else "")
        self.notes.setEnabled(saved)
        self.timestamp_button.setEnabled(saved)
        self.timestamp_button.setVisible(self._with_player)
        self._fill_thumb(video)
        self.status_label.setText("" if saved else t("details.save_to_take_notes"))
        self._dirty = False
        self._loading = False

    def _fill_thumb(self, video):
        if self._tokens is None or video is None:
            self.thumb.hide()
            return
        width = max(200, self.width() - 32)
        self.thumb.setPixmap(cover_pixmap(self._library.thumbnail_path(video), width, int(width * 9 / 16), 10, self._tokens))
        self.thumb.setFixedHeight(int(width * 9 / 16))
        self.thumb.show()

    def set_tokens(self, tokens):
        self._tokens = tokens
        self._fill_thumb(self._video)

    def _categories_text(self):
        if self._video is None or self._organize is None:
            return "—"
        names = {c.id: c.name for c in self._organize.org.categories()}
        ids = self._organize.org.video_category_ids(self._video.id)
        return ", ".join(sorted(names[i] for i in ids if i in names)) or self._tr.t("details.no_categories")

    def _fill_categories_menu(self, menu):
        menu.clear()
        if self._organize is None or self._video is None:
            return
        sub = self._organize.categories_menu([self._video.id], menu)
        for action in sub.actions():
            menu.addAction(action)
        menu._keep = sub

    def _on_library_changed(self):
        """Categorias ou o próprio vídeo mudaram em outro lugar: recarrega o que é metadado, sem perder o que está sendo digitado."""
        if self._video is None:
            return
        fresh = self._library.get(self._video.id)
        if fresh is None:
            self.set_video(None)
            return
        typed = self.notes.toPlainText() if self._dirty else None
        self._video = fresh
        self._fill()
        if typed is not None:
            self.notes.setPlainText(typed)
            self._dirty = True

    # -- anotações -------------------------------------------------------------------------
    def _refresh_markers(self):
        if not self._with_player:
            return
        marks = parse_markers(self.notes.toPlainText()) if self._video is not None else []
        self.markers.clear()
        for mark in marks:
            item = QListWidgetItem(f"{format_duration(mark.seconds) or '0:00'}   {mark.label}".rstrip())
            item.setData(Qt.UserRole, mark.seconds)
            self.markers.addItem(item)
        self.markers.setVisible(bool(marks))
        self.markers_hint.setVisible(not marks and self._video is not None)

    def _marker_clicked(self, item):
        self.seek_requested.emit(float(item.data(Qt.UserRole)))

    def _on_text_changed(self):
        self._refresh_markers()
        if self._loading or self._video is None:
            return
        self._dirty = True
        self.status_label.setText(self._tr.t("details.saving"))
        self._timer.start()

    def flush(self):
        """Grava as notas pendentes agora."""
        self._timer.stop()
        if not self._dirty or self._video is None:
            return
        self._dirty = False
        saved = self._library.set_notes(self._video.id, self.notes.toPlainText())
        if saved is not None:
            self._video.notes = saved
            self.status_label.setText(self._tr.t("details.saved"))

    def insert_timestamp(self, seconds):
        """Acrescenta '[m:ss] ' na posição do cursor."""
        if self._video is None:
            return
        self.notes.insertPlainText(f"[{format_duration(int(seconds)) or '0:00'}] ")
        self.notes.setFocus()

    def hideEvent(self, event):
        super().hideEvent(event)
        try:
            self.flush()
        except RuntimeError:  # destruição da janela
            pass

    # -- texto -----------------------------------------------------------------------------
    def retranslate(self):
        t = self._tr.t
        self.heading.setText(t("details.title").upper())
        for key, (label, _value) in self._rows.items():
            label.setText(t(f"details.{key}"))
        self.folder_button.setText(t("card.menu_folder"))
        self.categories_title.setText(t("details.categories").upper())
        self.categories_menu_button.setText(t("details.edit"))
        self.notes_title.setText(t("details.notes").upper())
        self.timestamp_button.setText(t("details.insert_time"))
        self.markers_title.setText(t("details.markers").upper())
        self.markers_hint.setText(t("details.no_markers"))
        self.notes.setPlaceholderText(t("details.notes_placeholder", limit=NOTES_LIMIT))
        self.notes.setAccessibleName(t("details.notes"))
        if self._video is not None or hasattr(self, "name_label"):
            self._fill()
