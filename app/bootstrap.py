import sys

from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication

from app import APP_NAME
from app.i18n import Translator
from app.logging_setup import install_excepthook
from app.infrastructure.providers.chain import ProviderChain
from app.infrastructure.providers.pytubefix_provider import PytubefixProvider
from app.infrastructure.providers.ytdlp_provider import YtdlpProvider
from app.services.settings_service import SettingsService
from app.services.storage_service import StorageManager
from app.styles.theme_manager import ThemeManager
from app.ui.main_window import MainWindow


def default_app_data_dir():
    return Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))


def default_providers(settings):
    return ProviderChain([PytubefixProvider(), YtdlpProvider()], order=settings.provider_order)


def create_window(app, settings=None, storage=None, providers=None, thumbnails=None, tools_getter=None, player_options=None):
    settings = settings or SettingsService()
    storage = storage or StorageManager(settings, default_app_data_dir())
    providers = providers or default_providers(settings)
    translator = Translator(settings.language)
    theme = ThemeManager(app, settings.theme)
    theme.apply()
    return MainWindow(settings, translator, theme, storage, providers, thumbnails, tools_getter, player_options)


def run():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    install_excepthook()
    window = create_window(app)
    window.show()
    if not window.ensure_storage():
        return 0
    window.start_background_checks()
    return app.exec()
