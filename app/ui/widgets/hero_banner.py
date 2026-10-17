from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

HERO_HEIGHT = 280


class HeroBanner(QFrame):
    """Vídeo em destaque do layout Streaming: miniatura grande ao fundo, título e botão de assistir.
    O véu escuro garante o contraste do texto branco sobre qualquer miniatura e qualquer tema."""

    open_requested = Signal(int)

    def __init__(self, tokens, video, thumbnail_path, kicker, meta, button_text, radius=16):
        super().__init__()
        self.setObjectName("hero")
        self.video = video
        self._radius = radius
        self._pixmap = QPixmap(str(thumbnail_path)) if thumbnail_path else QPixmap()
        self._tokens = tokens
        self.setFixedHeight(HERO_HEIGHT)
        self.setMinimumWidth(320)
        self.setAccessibleName(f"{kicker}: {video.title}")
        column = QVBoxLayout(self)
        column.setContentsMargins(28, 24, 28, 24)
        column.setSpacing(6)
        column.addStretch(1)
        self.kicker_label = QLabel(kicker.upper())
        self.kicker_label.setObjectName("heroKicker")
        self.title_label = QLabel(video.title)
        self.title_label.setObjectName("heroTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setMaximumWidth(560)
        self.meta_label = QLabel(meta)
        self.meta_label.setObjectName("heroMeta")
        self.meta_label.setVisible(bool(meta))
        row = QHBoxLayout()
        row.setContentsMargins(0, 8, 0, 0)
        self.play_button = QPushButton(button_text)
        self.play_button.setObjectName("primary")
        self.play_button.setCursor(Qt.PointingHandCursor)
        self.play_button.clicked.connect(lambda: self.open_requested.emit(video.id))
        row.addWidget(self.play_button)
        row.addStretch(1)
        for widget in (self.kicker_label, self.title_label, self.meta_label):
            column.addWidget(widget)
        column.addLayout(row)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(rect, self._radius, self._radius)
        p.setClipPath(clip)
        if self._pixmap.isNull():
            fill = QLinearGradient(rect.topLeft(), rect.bottomRight())
            fill.setColorAt(0, QColor(self._tokens["accent_soft"]) if self._tokens["accent_soft"].startswith("#") else QColor(self._tokens["accent"]).darker(300))
            fill.setColorAt(1, QColor("#000000"))
            p.fillRect(rect, fill)
        else:
            scaled = self._pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.drawPixmap(int((rect.width() - scaled.width()) / 2), int((rect.height() - scaled.height()) / 2), scaled)
        veil = QLinearGradient(rect.left(), 0, rect.right(), 0)
        veil.setColorAt(0, QColor(0, 0, 0, 235))
        veil.setColorAt(0.6, QColor(0, 0, 0, 150))
        veil.setColorAt(1, QColor(0, 0, 0, 40))
        p.fillRect(rect, veil)
        floor = QLinearGradient(0, rect.bottom() - 90, 0, rect.bottom())
        floor.setColorAt(0, QColor(0, 0, 0, 0))
        floor.setColorAt(1, QColor(0, 0, 0, 150))
        p.fillRect(rect, floor)
        p.end()
