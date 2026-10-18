import pytest
from PySide6.QtCore import QSettings

from app.domain import layouts
from app.services.settings_service import SettingsService


def test_six_layouts_with_classic_as_default():
    assert layouts.LAYOUT_CHOICES == ("classic", "streaming", "cinema", "manager", "workstation", "compact")
    assert layouts.DEFAULT_LAYOUT == "classic" and set(layouts.PROFILES) == set(layouts.LAYOUT_CHOICES)


def test_unknown_layout_falls_back_to_classic():
    assert layouts.profile_for("nope").key == "classic"


def test_each_layout_has_its_own_anatomy():
    p = layouts.PROFILES
    assert p["classic"].nav == "sidebar" and p["classic"].topbar == "full" and p["classic"].related and not p["classic"].up_next
    # streaming: sem sidebar nem barra de link; abas no topo, pôsteres e coluna "a seguir"
    assert p["streaming"].nav == "top" and p["streaming"].topbar == "none" and p["streaming"].up_next and p["streaming"].home == "streaming"
    assert p["streaming"].library_view == "posters" and p["streaming"].watch == "streaming"
    # cinema: navegação translúcida que some ao assistir, mural e player cheio
    assert p["cinema"].nav == "top" and p["cinema"].nav_for(True) == "none" and p["cinema"].topnav_style == "cinema"
    assert p["cinema"].home == "wall" and p["cinema"].library_view == "wall" and p["cinema"].watch == "cinema"
    # gerenciador: árvore, faixa de ações, tabela, prévia e barra de estado; páginas de lista viram consultas
    m = p["manager"]
    assert m.nav == "tree" and m.ribbon and m.statusbar and m.preview_pane and m.library_view == "table" and m.inline_filters
    assert m.redirect("home") == "library" and m.redirect("downloaded") == "library" and m.redirect("settings") is None
    # estação: barra de atividades, painéis, notas e barra de estado
    w = p["workstation"]
    assert w.nav == "icons" and w.library_list and w.details_panel and w.statusbar and w.watch == "workstation" and w.topbar == "slim"
    # compacto: janela pequena sem nenhuma das barras comuns
    c = p["compact"]
    assert c.compact_window and c.nav == "none" and c.topbar == "none" and c.watch == "compact" and not c.statusbar


def test_no_two_layouts_share_the_same_anatomy():
    keys = ("nav", "topbar", "topnav_style", "statusbar", "ribbon", "home", "library_view", "watch", "up_next", "preview_pane",
            "details_panel", "library_list", "compact_window", "inline_filters")
    shapes = [tuple(getattr(profile, k) for k in keys) for profile in layouts.PROFILES.values()]
    assert len(set(shapes)) == len(shapes)


def test_sidebar_mode_is_derived_from_the_navigation():
    p = layouts.PROFILES
    assert p["classic"].sidebar_for(False) == "full" and p["workstation"].sidebar_for(False) == "icons"
    for key in ("streaming", "cinema", "manager", "compact"):
        assert p[key].sidebar_for(False) == "hidden"


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
