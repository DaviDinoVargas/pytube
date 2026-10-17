from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.domain.errors import StorageError
from app.infrastructure.media.ffmpeg import MediaError
from app.services.storage_service import format_bytes
from app.ui.errors import describe_error


def _table(headers):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.ExtendedSelection)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.verticalHeader().hide()
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    table.setMinimumHeight(220)
    return table


class SpaceDialog(QDialog):
    """Espaço e arquivos: os maiores vídeos, os que sumiram e os arquivos soltos na pasta da biblioteca."""

    def __init__(self, translator, maintenance, library, tools_getter, on_open_video=None, parent=None):
        super().__init__(parent)
        self._tr = translator
        self._maint = maintenance
        self._library = library
        self._tools_getter = tools_getter
        self._on_open_video = on_open_video
        t = translator.t
        self.setWindowTitle(t("space.title"))
        self.setModal(True)
        self.setMinimumSize(640, 520)
        column = QVBoxLayout(self)
        column.setContentsMargins(24, 22, 24, 20)
        column.setSpacing(10)
        heading = QLabel(t("space.title"))
        heading.setObjectName("pageTitle")
        self.summary = QLabel()
        self.summary.setObjectName("pageSubtitle")
        column.addWidget(heading)
        column.addWidget(self.summary)
        self.tabs = QTabWidget()
        column.addWidget(self.tabs, 1)

        # maiores arquivos
        self.large_table = _table([t("space.col_title"), t("space.col_quality"), t("space.col_size")])
        self.large_table.itemSelectionChanged.connect(self._update_buttons)
        self.free_button = self._button("space.free", self.free_selected, primary=True)
        self.free_label = QLabel()
        self.free_label.setObjectName("cardMeta")
        self.tabs.addTab(self._tab(self.large_table, [self.free_button], note="space.free_note", extra=self.free_label), t("space.tab_large"))

        # ausentes
        self.missing_table = _table([t("space.col_title"), t("space.col_state")])
        self.missing_table.itemSelectionChanged.connect(self._update_buttons)
        self.locate_button = self._button("space.locate", self.locate_selected, primary=True)
        self.forget_button = self._button("space.forget", self.forget_selected)
        self.redownload_button = self._button("space.redownload", self.redownload_selected)
        self.verify_button = self._button("space.verify_again", self.verify)
        self.tabs.addTab(self._tab(self.missing_table, [self.locate_button, self.redownload_button, self.forget_button, self.verify_button]),
                         t("space.tab_missing"))

        # soltos
        self.orphan_table = _table([t("space.col_file"), t("space.col_size")])
        self.orphan_table.itemSelectionChanged.connect(self._update_buttons)
        self.delete_orphans_button = self._button("space.delete_orphans", self.delete_orphans)
        self.tabs.addTab(self._tab(self.orphan_table, [self.delete_orphans_button], note="space.orphans_note"), t("space.tab_orphans"))

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.hide()
        column.addWidget(self.status)
        close = QPushButton(t("backup.close"))
        close.setObjectName("secondary")
        close.clicked.connect(self.accept)
        column.addWidget(close, 0, Qt.AlignRight)
        self.refresh()

    # -- construção --------------------------------------------------------------------------
    def _button(self, key, slot, primary=False):
        button = QPushButton(self._tr.t(key))
        button.setObjectName("primary" if primary else "secondary")
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(slot)
        return button

    def _tab(self, table, buttons, note=None, extra=None):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 10, 0, 0)
        if note:
            label = QLabel(self._tr.t(note))
            label.setObjectName("pageSubtitle")
            label.setWordWrap(True)
            column.addWidget(label)
        column.addWidget(table, 1)
        row = QHBoxLayout()
        for b in buttons:
            row.addWidget(b)
        row.addStretch(1)
        if extra is not None:
            row.addWidget(extra)
        column.addLayout(row)
        return page

    # -- dados ---------------------------------------------------------------------------------
    def refresh(self):
        t = self._tr.t
        s = self._maint.summary()
        self.summary.setText(t("space.summary", files=s["video_files"], used=format_bytes(s["videos_bytes"]), free=format_bytes(s["free"])))
        self._fill_large()
        self._fill_missing()
        self._fill_orphans()
        self._update_buttons()

    def _cell(self, text, align_right=False, data=None):
        item = QTableWidgetItem(text)
        if align_right:
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if data is not None:
            item.setData(Qt.UserRole, data)
        return item

    def _fill_large(self):
        entries = self._maint.largest(100)
        self.large_table.setRowCount(len(entries))
        for row, e in enumerate(entries):
            self.large_table.setItem(row, 0, self._cell(e.video.title or e.video.url, data=e.video.id))
            self.large_table.setItem(row, 1, self._cell(e.video.local_quality or "—"))
            self.large_table.setItem(row, 2, self._cell(format_bytes(e.size), True, e.size))

    def _fill_missing(self):
        t = self._tr.t
        problems = self._maint.problems()
        self.missing_table.setRowCount(len(problems))
        for row, v in enumerate(problems):
            self.missing_table.setItem(row, 0, self._cell(v.title or v.url, data=v.id))
            self.missing_table.setItem(row, 1, self._cell(t(f"card.state_{v.local_status}")))

    def _fill_orphans(self):
        root = self._library.layout.videos
        orphans = self._maint.find_orphans()
        self.orphan_table.setRowCount(len(orphans))
        for row, o in enumerate(orphans):
            try:
                shown = str(o.path.relative_to(root))
            except ValueError:
                shown = o.path.name
            self.orphan_table.setItem(row, 0, self._cell(shown, data=str(o.path)))
            self.orphan_table.setItem(row, 1, self._cell(format_bytes(o.size), True, o.size))

    @staticmethod
    def _selected(table):
        rows = sorted({i.row() for i in table.selectedIndexes()})
        return [table.item(r, 0).data(Qt.UserRole) for r in rows]

    def _update_buttons(self):
        selected_large = self._selected(self.large_table)
        total = sum(self.large_table.item(r, 2).data(Qt.UserRole) for r in sorted({i.row() for i in self.large_table.selectedIndexes()}))
        self.free_button.setEnabled(bool(selected_large))
        self.free_label.setText(self._tr.t("space.will_free", size=format_bytes(total)) if selected_large else "")
        has_missing = bool(self._selected(self.missing_table))
        for b in (self.locate_button, self.redownload_button, self.forget_button):
            b.setEnabled(has_missing)
        self.delete_orphans_button.setEnabled(bool(self._selected(self.orphan_table)))

    def _say(self, text, ok=True):
        self.status.setText(text)
        self.status.setObjectName("statusOk" if ok else "statusError")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.status.show()

    def _confirm(self, body_key, ok_key, **values):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(self._tr.t("space.title"))
        box.setText(self._tr.t(body_key, **values))
        ok = box.addButton(self._tr.t(ok_key), QMessageBox.AcceptRole)
        box.addButton(self._tr.t("storage.cancel"), QMessageBox.RejectRole)
        box.exec()
        return box.clickedButton() is ok

    # -- ações ---------------------------------------------------------------------------------
    def free_selected(self):
        ids = self._selected(self.large_table)
        if not ids or not self._confirm("space.confirm_free", "space.free", count=len(ids)):
            return
        freed = self._maint.free_space_of(ids)
        self.refresh()
        self._say(self._tr.t("space.freed", size=format_bytes(freed)))

    def verify(self):
        counts = self._maint.verify_all()
        self.refresh()
        self._say(self._tr.t("space.verified", missing=counts["missing"] + counts["invalid"]))

    def locate_selected(self):
        ids = self._selected(self.missing_table)
        if not ids:
            return
        path, _ = QFileDialog.getOpenFileName(self, self._tr.t("space.locate"), "", "Vídeo (*.mp4 *.mkv *.webm *.m4v *.mov *.avi)")
        if not path:
            return
        try:
            self._maint.relocate(ids[0], Path(path), self._tools_getter())
        except (StorageError, MediaError) as exc:
            self._say(describe_error(self._tr, exc.code), ok=False)
            return
        self.refresh()
        self._say(self._tr.t("space.located"))

    def forget_selected(self):
        ids = self._selected(self.missing_table)
        for video_id in ids:
            self._library.clear_local_file(video_id)
        self.refresh()

    def redownload_selected(self):
        ids = self._selected(self.missing_table)
        if ids and self._on_open_video is not None:
            self._on_open_video(ids[0])
            self.accept()

    def delete_orphans(self):
        paths = self._selected(self.orphan_table)
        if not paths or not self._confirm("space.confirm_orphans", "space.delete_orphans", count=len(paths)):
            return
        freed = 0
        for path in paths:
            try:
                freed += self._maint.delete_orphan(path)
            except StorageError:
                continue
        self.refresh()
        self._say(self._tr.t("space.freed", size=format_bytes(freed)))
