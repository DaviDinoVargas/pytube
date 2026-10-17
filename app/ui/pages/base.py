from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget


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

        # O conteúdo rola quando a janela é menor que a página, em vez de espremer os componentes.
        content = QWidget()
        content.setObjectName("pageContent")
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(0, 0, 8, 16)
        self.body.setSpacing(16)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("pageScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setWidget(content)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 24, 0)
        root.setSpacing(4)
        root.addWidget(self.title)
        root.addWidget(self.subtitle)
        root.addSpacing(16)
        root.addWidget(self.scroll, 1)

    def retranslate(self):
        self.title.setText(self._tr.t(f"{self.key}.title"))
        self.subtitle.setText(self._tr.t(f"{self.key}.subtitle"))

    def set_tokens(self, tokens):
        """Páginas com elementos desenhados à mão (ícones) sobrescrevem este método."""

    def set_layout(self, profile):
        """Chamado quando o layout muda. Páginas que se organizam de outro jeito em algum layout sobrescrevem."""


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
