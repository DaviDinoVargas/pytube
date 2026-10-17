import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings

from app.services.settings_service import SettingsService


@pytest.fixture
def settings(tmp_path):
    return SettingsService(QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat))


@pytest.fixture(scope="session")
def qapp_args():
    return []
