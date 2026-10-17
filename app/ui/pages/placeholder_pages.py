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


class HomePage(_EmptyPage):
    key = "home"


class ContinuePage(_EmptyPage):
    key = "continue"


class LibraryPage(_EmptyPage):
    key = "library"


class DownloadedPage(_EmptyPage):
    key = "downloaded"


class PlaylistsPage(_EmptyPage):
    key = "playlists"


class CategoriesPage(_EmptyPage):
    key = "categories"


class HistoryPage(_EmptyPage):
    key = "history"


class DownloadsPage(_EmptyPage):
    key = "downloads"
