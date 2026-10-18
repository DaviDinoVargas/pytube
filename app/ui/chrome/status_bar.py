from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

MESSAGE_MS = 6000


class AppStatusBar(QFrame):
    """Barra de estado (layouts Gerenciador e Estação): resumo da biblioteca, seleção, espaço em disco, downloads em andamento e,
    no canto direito, a engrenagem das configurações."""

    def __init__(self, translator):
        super().__init__()
        self.setObjectName("appStatusBar")
        self.setFixedHeight(32)
        self._tr = translator
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(14, 0, 8, 0)
        self._row.setSpacing(18)
        self.summary = QLabel()
        self.message = QLabel()
        self.message.setObjectName("statusOk")
        self.message.hide()
        self.selection = QLabel()
        self.disk = QLabel()
        self.downloads = QLabel()
        for label in (self.summary, self.message, self.selection, self.disk, self.downloads):
            label.setObjectName(label.objectName() or "statusText")
        self._row.addWidget(self.summary)
        self._row.addWidget(self.message)
        self._row.addStretch(1)
        for widget in (self.selection, self.disk, self.downloads):
            self._row.addWidget(widget)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(MESSAGE_MS)
        self._timer.timeout.connect(lambda: self.show_message(""))

    def attach_gear(self, button):
        """A engrenagem muda de lugar entre o rodapé comum e esta barra, sempre no canto inferior direito."""
        self._row.addWidget(button)

    def set_summary(self, text):
        self.summary.setText(text)

    def set_selection(self, text):
        self.selection.setText(text)
        self.selection.setVisible(bool(text))

    def set_disk(self, text):
        self.disk.setText(text)

    def set_downloads(self, text):
        self.downloads.setText(text)
        self.downloads.setVisible(bool(text))

    def show_message(self, text, error=False):
        self.message.setObjectName("statusError" if error else "statusOk")
        self.message.style().unpolish(self.message)
        self.message.style().polish(self.message)
        self.message.setText(text)
        self.message.setVisible(bool(text))
        self._timer.stop()
        if text:
            self._timer.start()
