from PySide6.QtCore import QObject, QSize, Qt, Signal

from app.domain import layouts

COMPACT_SIZE = QSize(470, 760)
COMPACT_MIN = QSize(380, 520)


class LayoutController(QObject):
    """Aplica o layout escolhido à janela: sidebar, barra superior, janela compacta e a organização de cada página.
    A janela e as páginas não conhecem os layouts; só reagem ao perfil que recebem."""

    changed = Signal(str)

    def __init__(self, window):
        super().__init__(window)
        self._window = window
        self._key = layouts.DEFAULT_LAYOUT
        self._normal_geometry = None
        self._normal_min = None
        self._compact_active = False

    @property
    def key(self):
        return self._key

    @property
    def profile(self):
        return layouts.profile_for(self._key)

    def apply(self, key, go_landing=False):
        """Muda para o layout `key`. Com `go_landing`, abre a página inicial própria do layout."""
        if key not in layouts.LAYOUT_CHOICES:
            key = layouts.DEFAULT_LAYOUT
        profile = layouts.profile_for(key)
        window = self._window
        self._key = key
        window.settings_page.set_layout(key)
        self._set_compact_window(profile.compact_window)
        for page in window.pages.values():
            page.set_layout(profile)
        self._apply_chrome(window.current_page == "watch")
        if go_landing:
            window.show_landing(profile.landing)
        self.changed.emit(key)

    def on_page_changed(self, page_key):
        """Sidebar e barra superior de alguns layouts mudam enquanto o vídeo está aberto (ex.: modo cinema)."""
        self._apply_chrome(page_key == "watch")

    def _apply_chrome(self, watching):
        profile = self.profile
        window = self._window
        window.sidebar.set_mode(profile.sidebar_for(watching))
        window.top_bar.set_compact(profile.topbar == layouts.TOPBAR_COMPACT)
        window.top_bar.setVisible(not (profile.topbar_hidden_watching and watching))

    # -- janela compacta ---------------------------------------------------------------------
    def _set_compact_window(self, compact):
        window = self._window
        if compact and not self._compact_active:
            self._normal_geometry = window.geometry()
            self._normal_min = window.minimumSize()
            self._compact_active = True
            window.setMinimumSize(COMPACT_MIN)
            window.resize(COMPACT_SIZE)
            self.set_keep_on_top(window.settings.compact_on_top)
        elif not compact and self._compact_active:
            self._compact_active = False
            self.set_keep_on_top(False)
            window.setMinimumSize(self._normal_min)
            if self._normal_geometry is not None:
                window.setGeometry(self._normal_geometry)

    @property
    def keep_on_top(self):
        return bool(self._window.windowFlags() & Qt.WindowStaysOnTopHint)

    def set_keep_on_top(self, enabled):
        """Mantém a janela por cima das outras. Só faz sentido no layout compacto (nos demais é sempre desligado)."""
        window = self._window
        enabled = bool(enabled) and self._compact_active
        if enabled == self.keep_on_top:
            return
        visible = window.isVisible()
        window.setWindowFlag(Qt.WindowStaysOnTopHint, enabled)
        if visible:
            window.show()  # trocar a flag esconde a janela

    @property
    def compact_active(self):
        return self._compact_active
