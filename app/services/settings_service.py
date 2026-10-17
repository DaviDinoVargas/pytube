from PySide6.QtCore import QSettings

from app import APP_NAME
from app.i18n import DEFAULT_LANGUAGE, LANGUAGES
from app.styles.tokens import DEFAULT_THEME, THEME_CHOICES


class SettingsService:
    """Preferências da interface, persistidas em QSettings."""

    def __init__(self, store=None):
        self._s = store or QSettings(APP_NAME, APP_NAME)

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
