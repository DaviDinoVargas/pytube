from PySide6.QtCore import QSettings

from app import APP_NAME
from app.domain.layouts import DEFAULT_LAYOUT, LAYOUT_CHOICES
from app.i18n import DEFAULT_LANGUAGE, LANGUAGES
from app.styles.tokens import DEFAULT_THEME, THEME_CHOICES


class SettingsService:
    """Preferências da interface, persistidas em QSettings."""

    def __init__(self, store=None):
        self._s = store or QSettings(APP_NAME, APP_NAME)

    @property
    def location(self):
        """Arquivo ou chave onde as preferências estão gravadas."""
        return self._s.fileName()

    @property
    def language(self):
        value = self._s.value("general/language", DEFAULT_LANGUAGE)
        return value if value in LANGUAGES else DEFAULT_LANGUAGE

    @language.setter
    def language(self, value):
        self._s.setValue("general/language", value)

    @property
    def theme(self):
        value = self._s.value("general/theme", DEFAULT_THEME)
        return value if value in THEME_CHOICES else DEFAULT_THEME

    @theme.setter
    def theme(self, value):
        self._s.setValue("general/theme", value)

    @property
    def layout(self):
        value = self._s.value("general/layout", DEFAULT_LAYOUT)
        return value if value in LAYOUT_CHOICES else DEFAULT_LAYOUT

    @layout.setter
    def layout(self, value):
        self._s.setValue("general/layout", value)

    @property
    def queue_ids(self):
        """Fila de reprodução: ids dos vídeos, na ordem."""
        raw = str(self._s.value("queue/ids", "") or "")
        return tuple(int(x) for x in raw.split(",") if x.strip().isdigit())

    @queue_ids.setter
    def queue_ids(self, value):
        self._s.setValue("queue/ids", ",".join(str(int(i)) for i in value))

    @property
    def queue_current(self):
        raw = str(self._s.value("queue/current", "") or "")
        return int(raw) if raw.isdigit() else None

    @queue_current.setter
    def queue_current(self, value):
        self._s.setValue("queue/current", "" if value is None else str(int(value)))

    @property
    def layout_before_compact(self):
        """Layout a que o botão 'Janela completa' volta."""
        value = self._s.value("general/layout_before_compact", DEFAULT_LAYOUT)
        return value if value in LAYOUT_CHOICES and value != "compact" else DEFAULT_LAYOUT

    @layout_before_compact.setter
    def layout_before_compact(self, value):
        self._s.setValue("general/layout_before_compact", value)

    @property
    def watch_details(self):
        """Painel de detalhes aberto na tela do vídeo (layout clássico)."""
        return str(self._s.value("ui/watch_details", "false")).lower() == "true"

    @watch_details.setter
    def watch_details(self, value):
        self._s.setValue("ui/watch_details", bool(value))

    @property
    def compact_on_top(self):
        """No layout compacto, manter a janela por cima das outras."""
        return str(self._s.value("ui/compact_on_top", "true")).lower() == "true"

    @compact_on_top.setter
    def compact_on_top(self, value):
        self._s.setValue("ui/compact_on_top", bool(value))

    @property
    def sidebar_collapsed(self):
        return str(self._s.value("ui/sidebar_collapsed", "false")).lower() == "true"

    @sidebar_collapsed.setter
    def sidebar_collapsed(self, value):
        self._s.setValue("ui/sidebar_collapsed", bool(value))

    @property
    def last_page(self):
        return str(self._s.value("ui/last_page", "home"))

    @last_page.setter
    def last_page(self, value):
        self._s.setValue("ui/last_page", value)

    @property
    def storage_root(self):
        return str(self._s.value("storage/root", "") or "")

    @storage_root.setter
    def storage_root(self, value):
        self._s.setValue("storage/root", value)

    @property
    def storage_mode(self):
        return str(self._s.value("storage/mode", "folder"))

    @storage_mode.setter
    def storage_mode(self, value):
        self._s.setValue("storage/mode", value)

    @property
    def storage_format(self):
        return str(self._s.value("storage/format", "sqlite"))

    @storage_format.setter
    def storage_format(self, value):
        self._s.setValue("storage/format", value)

    @property
    def provider_order(self):
        raw = str(self._s.value("providers/order", "pytubefix,ytdlp"))
        return tuple(n for n in raw.split(",") if n)

    @provider_order.setter
    def provider_order(self, names):
        self._s.setValue("providers/order", ",".join(names))

    @property
    def download_consent(self):
        return str(self._s.value("downloads/consent", "false")).lower() == "true"

    @download_consent.setter
    def download_consent(self, value):
        self._s.setValue("downloads/consent", bool(value))

    @property
    def download_concurrent(self):
        try:
            return min(4, max(1, int(self._s.value("downloads/concurrent", 2))))
        except (TypeError, ValueError):
            return 2

    @download_concurrent.setter
    def download_concurrent(self, value):
        self._s.setValue("downloads/concurrent", int(value))

    @property
    def ffmpeg_path(self):
        return str(self._s.value("tools/ffmpeg_path", "") or "")

    @ffmpeg_path.setter
    def ffmpeg_path(self, value):
        self._s.setValue("tools/ffmpeg_path", value)

    @property
    def player_volume(self):
        try:
            return min(100, max(0, int(self._s.value("player/volume", 80))))
        except (TypeError, ValueError):
            return 80

    @player_volume.setter
    def player_volume(self, value):
        self._s.setValue("player/volume", int(value))

    @property
    def library_sort(self):
        from app.domain.query import SORTS

        value = str(self._s.value("library/sort", "newest"))
        return value if value in SORTS else "newest"

    @library_sort.setter
    def library_sort(self, value):
        self._s.setValue("library/sort", value)

    @property
    def library_view(self):
        value = str(self._s.value("library/view", "grid"))
        return value if value in ("grid", "list", "table") else "grid"

    @library_view.setter
    def library_view(self, value):
        self._s.setValue("library/view", value)

    @property
    def library_columns(self):
        """Colunas visíveis da tabela da biblioteca (None = as padrão)."""
        raw = str(self._s.value("library/columns", "") or "")
        return tuple(c for c in raw.split(",") if c) or None

    @library_columns.setter
    def library_columns(self, value):
        self._s.setValue("library/columns", ",".join(value))

    @property
    def library_table_header(self):
        """Larguras e ordem das colunas da tabela (estado do cabeçalho, em base64)."""
        return str(self._s.value("library/table_header", "") or "")

    @library_table_header.setter
    def library_table_header(self, value):
        self._s.setValue("library/table_header", value)

    @property
    def default_rate(self):
        try:
            rate = float(self._s.value("player/rate", 1.0))
        except (TypeError, ValueError):
            return 1.0
        return rate if rate in (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0) else 1.0

    @default_rate.setter
    def default_rate(self, value):
        self._s.setValue("player/rate", float(value))

    def _flag(self, key, default):
        raw = self._s.value(key, default)
        return str(raw).lower() == "true"

    @property
    def resume_enabled(self):
        return self._flag("player/resume", True)

    @resume_enabled.setter
    def resume_enabled(self, value):
        self._s.setValue("player/resume", bool(value))

    @property
    def autoplay_next(self):
        return self._flag("player/autoplay_next", True)

    @autoplay_next.setter
    def autoplay_next(self, value):
        self._s.setValue("player/autoplay_next", bool(value))

    @property
    def restore_last_page(self):
        return self._flag("ui/restore_last_page", True)

    @restore_last_page.setter
    def restore_last_page(self, value):
        self._s.setValue("ui/restore_last_page", bool(value))
