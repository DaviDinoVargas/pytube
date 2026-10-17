from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class Page(QWidget):
    """Página com título e subtítulo traduzíveis. As subclasses preenchem `self.body`."""

    key = ""

    def __init__(self, translator):
        super().__init__()
        self._tr = translator
        self.title = QLabel()
        self.title.setObjectName("pageTitle")
        self.subtitle = QLabel()
        self.subtitle.setObjectName("pageSubtitle")
        self.subtitle.setWordWrap(True)

        self.body = QVBoxLayout()
        self.body.setSpacing(16)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 16)
        root.setSpacing(4)
        root.addWidget(self.title)
        root.addWidget(self.subtitle)
        root.addSpacing(16)
        root.addLayout(self.body, 1)

    def retranslate(self):
        self.title.setText(self._tr.t(f"{self.key}.title"))
        self.subtitle.setText(self._tr.t(f"{self.key}.subtitle"))

    def set_tokens(self, tokens):
        """Páginas com elementos desenhados à mão (ícones) sobrescrevem este método."""


class EmptyState(QWidget):
    def __init__(self, translator, key):
        super().__init__()
        self._tr = translator
        self._key = key
        self.heading = QLabel()
        self.heading.setObjectName("emptyTitle")
        self.heading.setAlignment(Qt.AlignCenter)
        self.message = QLabel()
        self.message.setObjectName("emptyBody")
        self.message.setAlignment(Qt.AlignCenter)
        self.message.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addStretch(2)
        layout.addWidget(self.heading)
        layout.addWidget(self.message)
        layout.addStretch(3)
        self.retranslate()

    def retranslate(self):
        self.heading.setText(self._tr.t(f"{self._key}.empty_title"))
        self.message.setText(self._tr.t(f"{self._key}.empty_body"))
