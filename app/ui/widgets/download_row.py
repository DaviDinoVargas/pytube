from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QToolButton, QVBoxLayout

from app.domain.states import format_duration
from app.services import download_service as ds
from app.services.storage_service import format_bytes
from app.styles.icons import icon
from app.ui.errors import describe_error
from app.ui.widgets.video_card import cover_pixmap

THUMB = (96, 54)


def status_text(translator, task):
    t = translator.t
    if task.status == ds.DOWNLOADING:
        parts = [t("dl.status_downloading", label=task.label or "")]
        parts.append(f"{int(task.progress * 100)}%")
        if task.speed > 0:
            parts.append(f"{format_bytes(task.speed)}/s")
        if task.eta:
            parts.append(t("dl.eta", time=format_duration(task.eta) or "0:00"))
        return " · ".join(parts)
    if task.status == ds.COMPLETED:
        return t("dl.status_completed", label=task.label)
    if task.status == ds.FAILED:
        return t("dl.status_failed", reason=describe_error(translator, task.error_code))
    return t(f"dl.status_{task.status}")


class DownloadRow(QFrame):
    cancel_requested = Signal(int)
    retry_requested = Signal(int)
    open_requested = Signal(int)  # id do vídeo na biblioteca
    remove_requested = Signal(int)

    def __init__(self, translator, tokens, task, thumb_path=None):
        super().__init__()
        self.task = task
        self._tr = translator
        self._tokens = tokens
        self.setObjectName("card")
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(12)

        self.thumb = QLabel()
        self.thumb.setFixedSize(*THUMB)
        self.thumb.setPixmap(cover_pixmap(thumb_path, THUMB[0], THUMB[1], 8, tokens))
        row.addWidget(self.thumb)

        col = QVBoxLayout()
        col.setSpacing(4)
        self.title = QLabel(task.title)
        self.title.setObjectName("cardTitle")
        self.status = QLabel()
        self.status.setObjectName("cardMeta")
        self.status.setWordWrap(True)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        col.addWidget(self.title)
        col.addWidget(self.status)
        col.addWidget(self.bar)
        row.addLayout(col, 1)

        self.buttons = {}
        self._icon_names = {}
        for key, name, slot in (
            ("cancel", "close", lambda: self.cancel_requested.emit(self.task.id)),
            ("retry", "history", lambda: self.retry_requested.emit(self.task.id)),
            ("open", "play", lambda: self.open_requested.emit(self.task.video_id)),
            ("remove", "trash", lambda: self.remove_requested.emit(self.task.id)),
        ):
            button = QToolButton()
            button.setObjectName("iconButton")
            button.setIconSize(QSize(20, 20))
            button.setCursor(Qt.PointingHandCursor)
            button.setToolTip(translator.t(f"dl.{key}"))
            button.setAccessibleName(translator.t(f"dl.{key}"))
            button.clicked.connect(slot)
            self._icon_names[key] = name
            row.addWidget(button)
            self.buttons[key] = button
        self.update_from(task)

    def update_from(self, task):
        self.task = task
        self.status.setText(status_text(self._tr, task))
        self.bar.setValue(int(task.progress * 1000))
        state = "failed" if task.status == ds.FAILED else "done" if task.status == ds.COMPLETED else "active"
        if task.status in (ds.RESOLVING, ds.FINALIZING):
            self.bar.setRange(0, 0)  # indeterminado
        else:
            self.bar.setRange(0, 1000)
            self.bar.setValue(int(task.progress * 1000))
        if self.bar.property("state") != state:
            self.bar.setProperty("state", state)
            self.bar.style().unpolish(self.bar)
            self.bar.style().polish(self.bar)
        visible = {
            "cancel": task.status in ds.ACTIVE,
            "retry": task.status in (ds.FAILED, ds.CANCELLED),
            "open": task.status == ds.COMPLETED,
            "remove": task.finished,
        }
        for key, button in self.buttons.items():
            button.setVisible(visible[key])
            button.setIcon(icon(self._icon_names[key], self._tokens["text_secondary"]))
        self.bar.setVisible(task.status not in (ds.CANCELLED,))
