import os
import sys

from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths
from PySide6.QtWidgets import QApplication

from app import APP_NAME, APP_VERSION
from app.i18n import Translator
from app.logging_setup import install_excepthook
from app.infrastructure.providers.chain import ProviderChain
from app.infrastructure.providers.pytubefix_provider import PytubefixProvider
from app.infrastructure.providers.ytdlp_provider import YtdlpProvider
from app.services.settings_service import SettingsService
from app.services.storage_service import StorageManager
from app.styles.app_icon import app_icon
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


def _set_windows_app_id():
    """Faz o Windows agrupar a janela sob o ícone do DinoTube na barra de tarefas (e não sob o do Python)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DinoTube.App")
    except Exception:
        pass


def _prepare_glass_rendering():
    """Vidro cinza no Windows: a janela translúcida e o player online (Chromium) precisam usar a mesma renderização (RHI)
    desde o início. Sem isso o Qt recria a janela na primeira vez que o vídeo aparece, e o vídeo some e o vidro se perde.
    Só vale quando o tema salvo é o Vidro cinza; DINOTUBE_NO_RHI=1 desliga."""
    if sys.platform != "win32" or os.environ.get("DINOTUBE_NO_RHI"):
        return
    try:
        theme = QSettings(APP_NAME, APP_NAME).value("general/theme")
    except Exception:
        return
    if theme == "frost":
        os.environ.setdefault("QT_WIDGETS_RHI", "1")


def run():
    _prepare_glass_rendering()
    _set_windows_app_id()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(app_icon())
    install_excepthook()
    window = create_window(app)
    window.show()
    if not window.ensure_storage():
        return 0
    window.start_background_checks()
    return app.exec()
