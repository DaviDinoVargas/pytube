from app.ui.pages.base import EmptyState, Page


class _EmptyPage(Page):
    """Página que mostra apenas o estado vazio até a respectiva funcionalidade existir."""

    def __init__(self, translator):
        super().__init__(translator)
        self.empty = EmptyState(translator, self.key)
        self.body.addWidget(self.empty)
        self.retranslate()

    def retranslate(self):
        super().retranslate()
        if hasattr(self, "empty"):
            self.empty.retranslate()


class ContinuePage(_EmptyPage):
    key = "continue"


class HistoryPage(_EmptyPage):
    key = "history"
