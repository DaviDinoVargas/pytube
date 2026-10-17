import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Chromium do QtWebEngine em contêiner sem GPU/sandbox (só nos testes)
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu --disable-software-rasterizer")

import pytest
from PySide6.QtCore import QSettings

from app.services.settings_service import SettingsService


@pytest.fixture
def settings(tmp_path):
    return SettingsService(QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat))


@pytest.fixture(scope="session")
def qapp_args():
    return []


@pytest.fixture
def fake_provider():
    from tests.fakes import FakeProvider

    return FakeProvider("fake")


@pytest.fixture
def jpeg():
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    from PySide6.QtGui import QColor, QImage

    image = QImage(800, 450, QImage.Format_RGB32)
    image.fill(QColor("#336699"))
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    image.save(buf, "JPG")
    return bytes(data)


@pytest.fixture
def window_factory(qtbot, settings, tmp_path, fake_provider, jpeg):
    """Cria janelas sem rede: provedor simulado e miniaturas locais."""
    from PySide6.QtWidgets import QApplication

    from app.bootstrap import create_window
    from app.infrastructure.providers.chain import ProviderChain
    from app.services.storage_service import StorageManager
    from app.services.thumbnail_service import ThumbnailService

    def make(configure=True, storage=None):
        storage = storage or StorageManager(settings, tmp_path / "appdata")
        if configure and storage.status() != "ready":
            storage.configure(tmp_path / "lib", "folder", "sqlite")
        from tests.fakes import make_stub_player

        w = create_window(
            QApplication.instance(), settings, storage,
            ProviderChain([fake_provider]), ThumbnailService(lambda url: jpeg),
            player_options={"local_factory": make_stub_player, "online_factory": make_stub_player},
        )
        qtbot.addWidget(w)
        w.show()
        return w

    return make
