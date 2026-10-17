from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QFrame, QHBoxLayout, QMainWindow, QStackedWidget, QToolButton, QVBoxLayout, QWidget

from app import APP_NAME
from app.styles.icons import icon
from app.ui.pages.placeholder_pages import (
    CategoriesPage,
    ContinuePage,
    DownloadedPage,
    DownloadsPage,
    HistoryPage,
    HomePage,
    LibraryPage,
    PlaylistsPage,
)
from app.ui.pages.settings_page import SettingsPage
from app.ui.widgets.sidebar import Sidebar
from app.ui.widgets.url_bar import TopBar

DEFAULT_PAGE = "home"


class MainWindow(QMainWindow):
    def __init__(self, settings, translator, theme):
        super().__init__()
        self._settings = settings
        self._tr = translator
        self._theme = theme
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(900, 600)
        self.resize(1280, 800)

        tokens = theme.tokens
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        row = QHBoxLayout(root)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.sidebar = Sidebar(translator, tokens, settings.sidebar_collapsed)
        row.addWidget(self.sidebar)

        column = QVBoxLayout()
        column.setSpacing(0)
        self.top_bar = TopBar(translator, tokens)
        column.addWidget(self.top_bar)

        self.stack = QStackedWidget()
        self.pages = {}
        for page in (
            HomePage(translator),
            ContinuePage(translator),
            LibraryPage(translator),
            DownloadedPage(translator),
            PlaylistsPage(translator),
            CategoriesPage(translator),
            HistoryPage(translator),
            DownloadsPage(translator),
        ):
            self._add_page(page)
        self.settings_page = SettingsPage(translator, settings.language, settings.theme)
        self.settings_page.language_selected.connect(self._on_language)
        self.settings_page.theme_selected.connect(self._on_theme)
        self._add_page(self.settings_page)
        column.addWidget(self.stack, 1)

        # Rodapé com a engrenagem de configurações no canto inferior direito
        footer = QFrame()
        footer.setObjectName("footer")
        footer_row = QHBoxLayout(footer)
        footer_row.setContentsMargins(12, 4, 12, 8)
        footer_row.addStretch(1)
        self.settings_button = QToolButton()
        self.settings_button.setObjectName("iconButton")
        self.settings_button.setCheckable(True)
        self.settings_button.setIconSize(QSize(20, 20))
        self.settings_button.setCursor(Qt.PointingHandCursor)
        self.settings_button.clicked.connect(self._toggle_settings)
        footer_row.addWidget(self.settings_button)
        column.addWidget(footer)
        row.addLayout(column, 1)

        self.sidebar.page_selected.connect(self.show_page)
        self.sidebar.collapsed_changed.connect(lambda c: setattr(settings, "sidebar_collapsed", c))
        self.top_bar.video_requested.connect(self._on_video_requested)
        self._previous_page = DEFAULT_PAGE

        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.top_bar.focus_search)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.top_bar.focus_url)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=lambda: self.show_page("settings"))

        theme.theme_changed.connect(self._apply_tokens)
        self._apply_tokens()
        self.retranslate()
        last = settings.last_page
        self.show_page(last if last in self.pages else DEFAULT_PAGE)

    def _add_page(self, page):
        self.pages[page.key] = page
        self.stack.addWidget(page)

    @property
    def current_page(self):
        return self.stack.currentWidget().key

    def show_page(self, key):
        if key not in self.pages:
            return
        if key != "settings":
            self._previous_page = key
        self.stack.setCurrentWidget(self.pages[key])
        self.settings_button.setChecked(key == "settings")
        self.sidebar.select(key)
        self._settings.last_page = key

    def _toggle_settings(self):
        if self.current_page == "settings":
            self.show_page(self._previous_page)
        else:
            self.show_page("settings")

    def _on_video_requested(self, video_id):
        # A abertura do vídeo entra junto com a tela de reprodução
        pass

    def _on_language(self, code):
        self._settings.language = code
        self._tr.set_language(code)
        self.retranslate()

    def _on_theme(self, name):
        self._settings.theme = name
        self.settings_page.set_theme(name)
        self._theme.apply(name)

    def _apply_tokens(self):
        tokens = self._theme.tokens
        self.sidebar.set_tokens(tokens)
        self.top_bar.set_tokens(tokens)
        self.settings_button.setIcon(icon("settings", tokens["text_secondary"]))
        self.settings_page.set_tokens(tokens)

    def retranslate(self):
        label = self._tr.t("nav.settings")
        self.settings_button.setToolTip(f"{label} (Ctrl+,)")
        self.settings_button.setAccessibleName(label)
        self.sidebar.refresh()
        self.top_bar.retranslate()
        for page in self.pages.values():
            page.retranslate()
