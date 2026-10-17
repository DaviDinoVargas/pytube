import sys

from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication

from app import APP_NAME
from app.i18n import Translator
from app.services.settings_service import SettingsService
from app.services.storage_service import StorageManager
from app.styles.theme_manager import ThemeManager
from app.ui.main_window import MainWindow


def default_app_data_dir():
    return Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))


def create_window(app, settings=None, storage=None):
    settings = settings or SettingsService()
    storage = storage or StorageManager(settings, default_app_data_dir())
    translator = Translator(settings.language)
    theme = ThemeManager(app, settings.theme)
    theme.apply()
    return MainWindow(settings, translator, theme, storage)


def run():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    window = create_window(app)
    window.show()
    if not window.ensure_storage():
        return 0
    return app.exec()
