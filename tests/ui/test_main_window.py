import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.bootstrap import create_window
from app.services.storage_service import StorageManager
from app.styles.tokens import THEME_CHOICES, THEMES
from app.ui.widgets.sidebar import COLLAPSED_WIDTH, EXPANDED_WIDTH

VID = "dQw4w9WgXcQ"


def make(qtbot, settings):
    """Janela sem rede e com a biblioteca já configurada em uma pasta temporária."""
    from pathlib import Path

    from app.infrastructure.providers.chain import ProviderChain
    from app.services.thumbnail_service import ThumbnailService
    from tests.fakes import FakeProvider

    storage = StorageManager(settings, Path(settings.location).parent / "appdata")
    if storage.status() != "ready":
        storage.configure(Path(settings.location).parent / "lib", "folder", "sqlite")
    window = create_window(
        QApplication.instance(), settings, storage, ProviderChain([FakeProvider("fake")]), ThumbnailService(lambda u: b"")
    )
    qtbot.addWidget(window)
    window.show()
    return window


def test_starts_on_home_with_empty_state(qtbot, settings):
    w = make(qtbot, settings)
    assert w.current_page == "home"
    assert w.pages["home"].empty.heading.text() == "Sua biblioteca está vazia"


def test_navigation_via_sidebar(qtbot, settings):
    w = make(qtbot, settings)
    w.sidebar._buttons["downloads"].click()
    assert w.current_page == "downloads"
    assert settings.last_page == "downloads"


def test_gear_is_bottom_right_and_toggles_settings(qtbot, settings):
    w = make(qtbot, settings)
    gear = w.settings_button
    pos = gear.mapTo(w, gear.rect().bottomRight())
    assert pos.x() > w.width() * 0.9 and pos.y() > w.height() * 0.9
    gear.click()
    assert w.current_page == "settings"
    gear.click()
    assert w.current_page == "home"


def test_sidebar_collapse_is_persisted(qtbot, settings):
    w = make(qtbot, settings)
    assert w.sidebar.width() == EXPANDED_WIDTH
    w.sidebar._toggle.click()
    assert w.sidebar.width() == COLLAPSED_WIDTH
    assert settings.sidebar_collapsed is True
    assert make(qtbot, settings).sidebar.width() == COLLAPSED_WIDTH


def test_language_switch_translates_and_persists(qtbot, settings):
    w = make(qtbot, settings)
    w.show_page("settings")
    combo = w.settings_page.language_combo
    combo.setCurrentIndex(combo.findData("en"))
    assert w.pages["home"].empty.heading.text() == "Your library is empty"
    assert w.top_bar.open_button.text() == "Open video"
    assert settings.language == "en"
    assert make(qtbot, settings).top_bar.open_button.text() == "Open video"


def test_theme_switch_applies_stylesheet(qtbot, settings):
    w = make(qtbot, settings)
    w.show_page("settings")
    w.settings_page.theme_buttons["light"].click()
    assert settings.theme == "light"
    assert "#F6F7FB" in QApplication.instance().styleSheet()


@pytest.mark.parametrize("name", THEME_CHOICES)
def test_every_theme_can_be_selected_and_persisted(qtbot, settings, name):
    w = make(qtbot, settings)
    w.show_page("settings")
    w.settings_page.theme_buttons[name].click()
    assert settings.theme == name
    assert w.settings_page.theme_buttons[name].isChecked()
    assert QApplication.instance().styleSheet()
    reopened = make(qtbot, settings)
    reopened.show_page("settings")
    assert reopened.settings_page.theme_buttons[name].isChecked()


def test_ocean_uses_gradient_and_larger_radius(qtbot, settings):
    w = make(qtbot, settings)
    w.show_page("settings")
    w.settings_page.theme_buttons["ocean"].click()
    sheet = QApplication.instance().styleSheet()
    assert "qlineargradient" in sheet
    assert THEMES["ocean"]["radius"]["md"] > THEMES["forest"]["radius"]["md"]


def test_swatch_labels_follow_language(qtbot, settings):
    w = make(qtbot, settings)
    w.show_page("settings")
    combo = w.settings_page.language_combo
    combo.setCurrentIndex(combo.findData("en"))
    assert w.settings_page.theme_buttons["sunset"].accessibleName() == "Sunset"


def test_invalid_url_shows_error_and_valid_clears(qtbot, settings):
    w = make(qtbot, settings)
    bar = w.top_bar
    bar.url_input.setText("isso nao e link")
    bar.open_button.click()
    assert "Não foi possível reconhecer" in bar.feedback.text()
    assert bar.url_input.property("invalid") is True
    with qtbot.waitSignal(bar.video_requested) as sig:
        bar.url_input.setText(f"https://youtu.be/{VID}")
        bar.open_button.click()
    assert sig.args == [VID]
    assert bar.url_input.property("invalid") is False


def test_keyboard_shortcuts_focus_fields(qtbot, settings):
    w = make(qtbot, settings)
    w.activateWindow()
    qtbot.waitUntil(w.isActiveWindow)
    qtbot.keyClick(w, Qt.Key_K, Qt.ControlModifier)
    assert w.focusWidget() is w.top_bar.search_input
    qtbot.keyClick(w, Qt.Key_L, Qt.ControlModifier)
    assert w.focusWidget() is w.top_bar.url_input
    qtbot.keyClick(w, Qt.Key_Comma, Qt.ControlModifier)
    assert w.current_page == "settings"


def test_sidebar_highlight_is_cleared_on_settings(qtbot, settings):
    w = make(qtbot, settings)
    assert w.sidebar._buttons["home"].isChecked()
    w.show_page("settings")
    assert not any(b.isChecked() for b in w.sidebar._buttons.values())
    w.show_page("library")
    assert w.sidebar._buttons["library"].isChecked()
