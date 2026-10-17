from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QToolButton, QVBoxLayout, QWidget

from app.styles.icons import icon


class _RowScroll(QScrollArea):
    """Rola na horizontal. A roda vertical do mouse passa para a página (a fileira não "rouba" a rolagem)."""

    def wheelEvent(self, event):
        delta = event.angleDelta()
        if abs(delta.x()) > abs(delta.y()):
            bar = self.horizontalScrollBar()
            bar.setValue(bar.value() - delta.x())
            event.accept()
        else:
            event.ignore()


class ThumbRow(QWidget):
    """Fileira horizontal de itens com título, "ver tudo" opcional e setas para rolar."""

    def __init__(self, tokens, title_widget, items, see_all=None, prev_label="", next_label=""):
        super().__init__()
        self._tokens = tokens
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)
        head = QHBoxLayout()
        head.setSpacing(6)
        head.addWidget(title_widget)
        head.addStretch(1)
        if see_all is not None:
            head.addWidget(see_all)
        self.prev_button = self._arrow("chevron_left", prev_label, -1)
        self.next_button = self._arrow("chevron_right", next_label, 1)
        head.addWidget(self.prev_button)
        head.addWidget(self.next_button)
        column.addLayout(head)

        content = QWidget()
        content.setObjectName("rowContent")
        self._row = QHBoxLayout(content)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(14)
        self.items = list(items)
        for item in self.items:
            self._row.addWidget(item, 0, Qt.AlignTop)
        self._row.addStretch(1)
        self.scroll = _RowScroll()
        self.scroll.setObjectName("rowScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setWidget(content)
        self.scroll.setStyleSheet("QScrollArea#rowScroll, QWidget#rowContent { background: transparent; }")
        height = max((item.sizeHint().height() for item in self.items), default=0)
        self.scroll.setFixedHeight(height + 6)
        column.addWidget(self.scroll)
        self._animation = QPropertyAnimation(self.scroll.horizontalScrollBar(), b"value", self)
        self._animation.setDuration(220)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self.scroll.horizontalScrollBar().rangeChanged.connect(lambda *_: self._sync_arrows())
        self.scroll.horizontalScrollBar().valueChanged.connect(lambda *_: self._sync_arrows())
        self._sync_arrows()

    def _arrow(self, icon_name, label, direction):
        button = QToolButton()
        button.setObjectName("iconButton")
        button.setIcon(icon(icon_name, self._tokens["text_secondary"], 18))
        button.setToolTip(label)
        button.setAccessibleName(label)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(lambda _=False, d=direction: self.scroll_by(d))
        return button

    def scroll_by(self, direction):
        bar = self.scroll.horizontalScrollBar()
        target = bar.value() + direction * int(self.scroll.viewport().width() * 0.85)
        self._animation.stop()
        self._animation.setStartValue(bar.value())
        self._animation.setEndValue(max(bar.minimum(), min(bar.maximum(), target)))
        self._animation.start()

    def _sync_arrows(self):
        bar = self.scroll.horizontalScrollBar()
        scrollable = bar.maximum() > bar.minimum()
        self.prev_button.setVisible(scrollable)
        self.next_button.setVisible(scrollable)
        self.prev_button.setEnabled(bar.value() > bar.minimum())
        self.next_button.setEnabled(bar.value() < bar.maximum())


def link_button(text, slot):
    button = QPushButton(text)
    button.setObjectName("linkButton")
    button.setCursor(Qt.PointingHandCursor)
    button.clicked.connect(slot)
    return button


def title_label(text, rich=False):
    label = QLabel()
    label.setObjectName("sectionTitle")
    if rich:
        label.setTextFormat(Qt.RichText)
    label.setText(text)
    return label
