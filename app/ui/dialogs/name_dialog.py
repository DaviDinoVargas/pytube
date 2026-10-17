from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton, QDialog, QHBoxLayout, QLabel, QLayout, QLineEdit, QPushButton, QVBoxLayout

from app.domain.errors import StorageError
from app.services.organization_service import MAX_NAME
from app.ui.errors import describe_error

PALETTE = ("#8B7CF6", "#5B9BFF", "#2EC4B6", "#4ADE80", "#F2C14E", "#F59E5B", "#EF6F6C", "#E879F9")


class ColorSwatch(QAbstractButton):
    def __init__(self, color, label):
        super().__init__()
        self.color = color
        self.setCheckable(True)
        self.setFixedSize(QSize(28, 28))
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(label)
        self.setAccessibleName(label)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.color:
            p.setBrush(QColor(self.color))
            p.setPen(Qt.NoPen)
            p.drawEllipse(self.rect().adjusted(4, 4, -4, -4))
        else:
            p.setPen(QColor(150, 150, 150))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(self.rect().adjusted(4, 4, -4, -4))
            p.drawLine(8, 20, 20, 8)
        if self.isChecked():
            p.setBrush(Qt.NoBrush)
            p.setPen(QColor(255, 255, 255))
            p.drawEllipse(self.rect().adjusted(1, 1, -1, -1))
        if self.hasFocus():
            p.setPen(QColor(120, 160, 255))
            p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 6, 6)


class NameDialog(QDialog):
    """Criar ou editar uma categoria (nome, descrição, cor) ou uma playlist (nome, descrição)."""

    def __init__(self, translator, title_key, submit, with_color=False, name="", description="", color=None, parent=None):
        super().__init__(parent)
        self._tr = translator
        self._submit = submit  # chamada com (nome, descrição, cor); levanta StorageError se for inválido
        self._color = color
        t = translator.t
        self.setWindowTitle(t(title_key))
        self.setModal(True)
        self.setFixedWidth(440)
        column = QVBoxLayout(self)
        column.setContentsMargins(24, 22, 24, 20)
        column.setSpacing(10)
        column.setSizeConstraint(QLayout.SetFixedSize)
        heading = QLabel(t(title_key))
        heading.setObjectName("pageTitle")
        column.addWidget(heading)

        column.addWidget(self._label(t("dialog.name")))
        self.name_input = QLineEdit(name)
        self.name_input.setMaxLength(MAX_NAME + 20)  # a regra dos 60 é do serviço; aqui o erro é explicado
        self.name_input.setAccessibleName(t("dialog.name"))
        column.addWidget(self.name_input)
        column.addWidget(self._label(t("dialog.description")))
        self.description_input = QLineEdit(description)
        self.description_input.setAccessibleName(t("dialog.description"))
        column.addWidget(self.description_input)

        self.swatches = []
        if with_color:
            column.addWidget(self._label(t("dialog.color")))
            row = QHBoxLayout()
            row.setSpacing(4)
            for value in (None,) + PALETTE:
                swatch = ColorSwatch(value, value or t("dialog.color_none"))
                swatch.setChecked((value or None) == (color or None))
                swatch.clicked.connect(lambda _=False, c=value: self._pick(c))
                row.addWidget(swatch)
                self.swatches.append(swatch)
            row.addStretch(1)
            column.addLayout(row)

        self.error_label = QLabel()
        self.error_label.setObjectName("statusError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        column.addWidget(self.error_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.cancel_button = QPushButton(t("storage.cancel"))
        self.cancel_button.setObjectName("secondary")
        self.cancel_button.clicked.connect(self.reject)
        self.save_button = QPushButton(t("dialog.save"))
        self.save_button.setObjectName("primary")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._save)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.save_button)
        column.addLayout(buttons)
        self.name_input.textChanged.connect(lambda _t: self.error_label.hide())
        self.name_input.returnPressed.connect(self._save)

    @staticmethod
    def _label(text):
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def _pick(self, color):
        self._color = color
        for swatch in self.swatches:
            swatch.setChecked(swatch.color == color)

    @property
    def color(self):
        return self._color

    def _save(self):
        try:
            self._submit(self.name_input.text(), self.description_input.text(), self._color)
        except StorageError as exc:
            self.error_label.setText(describe_error(self._tr, exc.code))
            self.error_label.show()
            return
        self.accept()
