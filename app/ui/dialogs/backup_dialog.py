from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QLocale, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.domain.errors import StorageError
from app.ui.errors import describe_error


class BackupDialog(QDialog):
    """Backups da biblioteca: criar, restaurar, exportar e importar. Só os dados; os vídeos baixados não entram."""

    def __init__(self, translator, backups, parent=None):
        super().__init__(parent)
        self._tr = translator
        self._backups = backups
        t = translator.t
        self.setWindowTitle(t("backup.title"))
        self.setModal(True)
        self.setMinimumWidth(560)
        column = QVBoxLayout(self)
        column.setContentsMargins(24, 22, 24, 20)
        column.setSpacing(10)
        heading = QLabel(t("backup.title"))
        heading.setObjectName("pageTitle")
        note = QLabel(t("backup.note"))
        note.setObjectName("pageSubtitle")
        note.setWordWrap(True)
        column.addWidget(heading)
        column.addWidget(note)
        self.list = QListWidget()
        self.list.setMinimumHeight(180)
        self.list.setAccessibleName(t("backup.title"))
        column.addWidget(self.list)

        row = QHBoxLayout()
        self.create_button = self._button("backup.create", self.create_backup, primary=True)
        self.restore_button = self._button("backup.restore", self.restore_selected)
        row.addWidget(self.create_button)
        row.addWidget(self.restore_button)
        row.addStretch(1)
        column.addLayout(row)
        row2 = QHBoxLayout()
        self.export_button = self._button("backup.export", self.export_file)
        self.import_button = self._button("backup.import", self.import_file)
        self.csv_button = self._button("backup.export_csv", self.export_csv)
        for b in (self.export_button, self.import_button, self.csv_button):
            row2.addWidget(b)
        row2.addStretch(1)
        column.addLayout(row2)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.hide()
        column.addWidget(self.status)
        close = QPushButton(t("backup.close"))
        close.setObjectName("secondary")
        close.clicked.connect(self.accept)
        column.addWidget(close, 0, Qt.AlignRight)
        self.list.itemSelectionChanged.connect(self._update_buttons)
        self.refresh()

    def _button(self, key, slot, primary=False):
        button = QPushButton(self._tr.t(key))
        button.setObjectName("primary" if primary else "secondary")
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(slot)
        return button

    # -- lista ---------------------------------------------------------------------------------
    def _label(self, info):
        t = self._tr.t
        kind = t(f"backup.kind_{info.kind}") if info.kind in ("manual", "auto", "pre-restore", "export") else info.kind
        try:
            moment = datetime.fromisoformat(info.created_at).astimezone()
            when = QLocale("pt_BR" if self._tr.language == "pt-BR" else "en_US").toString(moment, QLocale.ShortFormat)
        except ValueError:
            when = "?"
        count = t("library.count_one") if info.videos == 1 else t("library.count_many", count=info.videos)
        return f"{kind}  ·  {when}  ·  {count}"

    def refresh(self):
        self.list.clear()
        for info in self._backups.list():
            item = QListWidgetItem(self._label(info))
            item.setData(Qt.UserRole, str(info.path))
            self.list.addItem(item)
        self._update_buttons()

    def _update_buttons(self):
        self.restore_button.setEnabled(bool(self.list.selectedItems()))

    def selected_path(self):
        items = self.list.selectedItems()
        return Path(items[0].data(Qt.UserRole)) if items else None

    # -- mensagens -----------------------------------------------------------------------------
    def _say(self, text, ok=True):
        self.status.setText(text)
        self.status.setObjectName("statusOk" if ok else "statusError")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.status.show()

    def _fail(self, exc):
        self._say(describe_error(self._tr, exc.code if isinstance(exc, StorageError) else "unknown"), ok=False)

    def _confirm(self, key):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(self._tr.t("backup.restore"))
        box.setText(self._tr.t(key))
        ok = box.addButton(self._tr.t("backup.restore"), QMessageBox.AcceptRole)
        box.addButton(self._tr.t("storage.cancel"), QMessageBox.RejectRole)
        box.exec()
        return box.clickedButton() is ok

    # -- ações ---------------------------------------------------------------------------------
    def create_backup(self):
        try:
            path = self._backups.create("manual")
        except (StorageError, OSError) as exc:
            self._fail(exc if isinstance(exc, StorageError) else StorageError("io_error", str(exc)))
            return
        self.refresh()
        self._say(self._tr.t("backup.created", name=path.name))

    def restore_selected(self):
        path = self.selected_path()
        if path is not None:
            self._restore(path)

    def _restore(self, path):
        if not self._confirm("backup.confirm_restore"):
            return
        try:
            result = self._backups.restore(path)
        except StorageError as exc:
            self._fail(exc)
            return
        self.refresh()
        self._say(self._tr.t("backup.restored", count=result["videos"]))

    def export_file(self):
        target, _ = QFileDialog.getSaveFileName(self, self._tr.t("backup.export"), "dinotube-biblioteca.json", "JSON (*.json)")
        if target:
            try:
                self._backups.export_to(target)
            except (StorageError, OSError) as exc:
                self._fail(exc if isinstance(exc, StorageError) else StorageError("io_error", str(exc)))
                return
            self._say(self._tr.t("backup.exported", name=Path(target).name))

    def import_file(self):
        source, _ = QFileDialog.getOpenFileName(self, self._tr.t("backup.import"), "", "JSON (*.json)")
        if source:
            self._restore(Path(source))

    def export_csv(self):
        target, _ = QFileDialog.getSaveFileName(self, self._tr.t("backup.export_csv"), "dinotube-lista.csv", "CSV (*.csv)")
        if target:
            try:
                self._backups.export_csv(target)
            except (StorageError, OSError) as exc:
                self._fail(exc if isinstance(exc, StorageError) else StorageError("io_error", str(exc)))
                return
            self._say(self._tr.t("backup.exported", name=Path(target).name))
