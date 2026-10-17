from PySide6.QtCore import QSettings

from app import APP_NAME
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
