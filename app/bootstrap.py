import sys

from PySide6.QtWidgets import QApplication

from app import APP_NAME
from app.i18n import Translator
from app.services.settings_service import SettingsService
from app.styles.theme_manager import ThemeManager
from app.ui.main_window import MainWindow


def create_window(app, settings=None):
    settings = settings or SettingsService()
    translator = Translator(settings.language)
    theme = ThemeManager(app, settings.theme)
    theme.apply()
    return MainWindow(settings, translator, theme)


def run():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    window = create_window(app)
    window.show()
    return app.exec()
