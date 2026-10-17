import pytest
from PySide6.QtCore import QSettings

from app.domain import layouts
from app.services.settings_service import SettingsService


def test_six_layouts_with_classic_as_default():
    assert layouts.LAYOUT_CHOICES == ("classic", "streaming", "cinema", "manager", "workstation", "compact")
    assert layouts.DEFAULT_LAYOUT == "classic" and set(layouts.PROFILES) == set(layouts.LAYOUT_CHOICES)


def test_unknown_layout_falls_back_to_classic():
    assert layouts.profile_for("nope").key == "classic"


def test_each_layout_has_its_own_structure():
    p = layouts.PROFILES
    assert p["classic"].sidebar == "full" and p["classic"].related and not p["classic"].details_panel
    assert p["streaming"].home == "streaming"
    assert p["cinema"].watch == "cinema" and p["cinema"].sidebar_for(True) == "hidden" and p["cinema"].topbar_hidden_watching
    assert p["manager"].library_view == "table" and p["manager"].landing == "library"
    assert p["workstation"].library_list and p["workstation"].details_panel and p["workstation"].watch == "workstation"
    assert p["compact"].compact_window and p["compact"].sidebar == "hidden" and p["compact"].topbar == "compact"


def test_sidebar_for_defaults_to_the_same_mode_when_watching():
    assert layouts.PROFILES["streaming"].sidebar_for(True) == "icons"
    assert layouts.PROFILES["cinema"].sidebar_for(False) == "icons"


def test_setting_persists_and_ignores_garbage(tmp_path):
    path = str(tmp_path / "p.ini")
    s = SettingsService(QSettings(path, QSettings.IniFormat))
    assert s.layout == "classic"
    s.layout = "workstation"
    assert SettingsService(QSettings(path, QSettings.IniFormat)).layout == "workstation"
    s.layout = "xyz"
    assert s.layout == "classic"


@pytest.mark.parametrize("key", layouts.LAYOUT_CHOICES)
def test_every_layout_is_translated(key):
    from app.i18n import _STRINGS

    for language in _STRINGS.values():
        assert f"layout.{key}" in language and f"layout.{key}_desc" in language
