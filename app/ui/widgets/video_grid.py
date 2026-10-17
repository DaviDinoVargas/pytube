from PySide6.QtWidgets import QWidget

from app.ui.widgets.flow_layout import FlowLayout


class VideoGrid(QWidget):
    """Conjunto de cards que quebra em linhas conforme a largura disponível."""

    def __init__(self, gap=16):
        super().__init__()
        self._cards = []
        self._flow = FlowLayout(self, gap, gap)

    @property
    def cards(self):
        return list(self._cards)

    def set_cards(self, cards):
        for card in self._cards:
            self._flow.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._cards = list(cards)
        for card in self._cards:
            self._flow.addWidget(card)
        self._flow.invalidate()

    def columns(self):
        """Quantidade de cards na primeira linha, com base na posição real deles."""
        if not self._cards:
            return 0
        top = self._cards[0].y()
        return sum(1 for c in self._cards if c.y() == top)
