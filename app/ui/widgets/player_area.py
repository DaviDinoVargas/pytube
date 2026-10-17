from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy, QVBoxLayout

from app.styles.icons import icon

MAX_WIDTH = 1000


class PlayerArea(QFrame):
    """Área 16:9 do vídeo. Mostra a miniatura e as opções disponíveis para abrir o vídeo."""

    browser_requested = Signal()

    def __init__(self, translator, tokens):
        super().__init__()
        self.setObjectName("playerArea")
        self._tr = translator
        self._tokens = tokens
        self._pixmap = QPixmap()
        self.setMaximumWidth(MAX_WIDTH)
        policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

        column = QVBoxLayout(self)
        column.setAlignment(Qt.AlignCenter)
        self.message = QLabel()
        self.message.setObjectName("playerMessage")
        self.message.setAlignment(Qt.AlignCenter)
        self.message.setWordWrap(True)
        self.browser_button = QPushButton()
        self.browser_button.setObjectName("primary")
        self.browser_button.setCursor(Qt.PointingHandCursor)
        self.browser_button.clicked.connect(self.browser_requested)
        column.addWidget(self.message, 0, Qt.AlignCenter)
        column.addSpacing(8)
        column.addWidget(self.browser_button, 0, Qt.AlignCenter)
        self.retranslate()

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return int(min(width, MAX_WIDTH) * 9 / 16)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # QStackedWidget ignora altura-por-largura; a proporção 16:9 é imposta aqui
        height = max(180, self.heightForWidth(self.width()))
        if self.height() != height:
            self.setFixedHeight(height)

    def set_thumbnail(self, path):
        self._pixmap = QPixmap(str(path)) if path else QPixmap()
        self.update()

    def set_tokens(self, tokens):
        self._tokens = tokens
        self.browser_button.setIcon(icon("external", tokens["text_on_accent"], 18))
        self.update()

    def retranslate(self):
        self.message.setText(self._tr.t("watch.player_placeholder"))
        self.browser_button.setText(self._tr.t("watch.open_browser"))

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(rect, 14, 14)
        p.setClipPath(clip)
        p.fillRect(rect, QColor("#000000"))
        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.drawPixmap((self.width() - scaled.width()) // 2, (self.height() - scaled.height()) // 2, scaled)
        p.fillRect(rect, QColor(0, 0, 0, 150))
        p.end()
