import re

import pytest

from app.i18n import _STRINGS
from app.styles.contrast import flatten_hex, ratio
from app.styles.tokens import THEME_CHOICES, THEMES

V12_THEMES = (
    "minimal", "cinema", "glass", "neumorphism", "nord", "dracula", "terminal", "pixel",
    "luxury", "pastel", "editorial", "fluent", "cyberpunk", "mono", "skeuo", "earthy",
)
BASES = ("bg_start", "bg_end")  # extremos do gradiente de fundo: o pior caso de contraste está em um deles
SURFACES = ("background", "surface", "surface_elevated", "sidebar_bg", "topbar_bg", "input_bg", "surface_hover")


def _flat(t, key, under):
    """Cor do token já composta sobre o fundo (tokens translúcidos viram a cor que o usuário realmente vê)."""
    return flatten_hex(t[key], under)


def _unders(t):
    unders = {t["bg_start"], t["bg_end"], t["background"]}
    if t["translucent"]:  # janela translúcida: o pior caso é uma área de trabalho clara por trás
        for desk in ("#FFFFFF", "#F0E68C", "#000000"):
            unders |= {flatten_hex(t["bg_start"], desk), flatten_hex(t["bg_end"], desk)}
    return unders


def _solid(value):
    return bool(re.fullmatch(r"#[0-9A-Fa-f]{6}", value))


def test_all_themes_define_same_tokens():
    keys = set(THEMES["dark"])
    for name, tokens in THEMES.items():
        assert set(tokens) == keys, name


def test_system_is_a_choice_and_not_a_theme():
    assert "system" in THEME_CHOICES and "system" not in THEMES


def test_the_sixteen_new_themes_exist_and_nothing_was_lost():
    assert set(V12_THEMES) <= set(THEMES)
    assert {"dark", "light", "ocean", "forest", "sunset"} <= set(THEMES)
    assert len(THEMES) == 22 and THEME_CHOICES[0] == "system"


def test_every_theme_is_translated_in_both_languages():
    for language in _STRINGS.values():
        for name in THEME_CHOICES:
            assert f"theme.{name}" in language


@pytest.mark.parametrize("name", THEMES)
def test_text_contrast_meets_wcag_aa_on_every_surface(name):
    t = THEMES[name]
    for under in _unders(t):
        for surface in SURFACES:
            bg = _flat(t, surface, under)
            for text in ("text_primary", "text_secondary"):
                assert ratio(t[text], bg) >= 4.5, (name, text, surface, under)


@pytest.mark.parametrize("name", THEMES)
def test_text_on_accent_is_readable_in_every_state(name):
    t = THEMES[name]
    for accent in ("accent", "accent_hover"):
        assert ratio(t["text_on_accent"], t[accent]) >= 4.5, (name, accent)
    if t["btn_top"] != t["accent"]:  # gradiente dos botões: texto escuro sobre as duas pontas
        for end in ("btn_top", "btn_bottom"):
            assert ratio(t["text_on_accent"], t[end]) >= 4.5, (name, end)


@pytest.mark.parametrize("name", THEMES)
def test_accent_text_status_colors_and_focus_are_readable(name):
    t = THEMES[name]
    for under in _unders(t):
        for surface in ("background", "surface", "surface_elevated"):
            bg = _flat(t, surface, under)
            assert ratio(t["accent_fg"], bg) >= 4.5, (name, "accent_fg", surface)
            assert ratio(t["success"], bg) >= 4.5, (name, "success", surface)
            assert ratio(t["error"], bg) >= 4.5, (name, "error", surface)
            assert ratio(t["focus"], bg) >= 3, (name, "focus", surface)  # indicador de foco: 3:1 (WCAG 1.4.11)
    # selos de aviso e erro levam texto escuro por cima
    for status in ("warning", "error"):
        assert ratio(t[f"text_on_{status}"], t[status]) >= 4.5, (name, status)
    assert ratio(t["warning"], _flat(t, "surface", t["background"])) >= 3, (name, "warning border")


@pytest.mark.parametrize("name", THEMES)
def test_downloaded_state_keeps_text_readable(name):
    t = THEMES[name]
    for under in _unders(t):
        bg = _flat(t, "downloaded_bg", _flat(t, "surface", under))
        for text in ("text_primary", "text_secondary"):
            assert ratio(t[text], bg) >= 4.5, (name, text)
    assert ratio(t["text_primary"], _flat(t, "accent_soft", t["background"])) >= 4.5
    assert ratio(t["text_on_downloaded"], t["downloaded_border"]) >= 4.5, (name, "badge")


@pytest.mark.parametrize("name", THEMES)
def test_solid_tokens_are_valid_hex(name):
    t = THEMES[name]
    for key in ("background", "surface_elevated", "text_primary", "text_secondary", "accent", "accent_hover", "success", "warning", "error"):
        assert _solid(t[key]), (name, key)


@pytest.mark.parametrize("name", THEMES)
def test_player_progress_is_visible_on_the_controls_bar(name):
    t = THEMES[name]
    assert ratio(t["progress"], t["surface_elevated"]) >= 3, name
    assert ratio(t["border"], t["surface_elevated"]) <= 12  # a calha do slider precisa existir sem competir com a barra


def test_pixel_art_has_square_corners_and_thick_borders_and_terminal_is_monospace():
    assert THEMES["pixel"]["border_width"] == 2 and set(THEMES["pixel"]["radius"].values()) == {0}
    assert "mono" in THEMES["terminal"]["font"].lower()
    assert "serif" in THEMES["luxury"]["title_font"] and "serif" in THEMES["editorial"]["title_font"]
    assert THEMES["fluent"]["radius"]["sm"] == 4 and THEMES["fluent"]["radius"]["md"] == 8


def test_relief_themes_declare_light_and_shadow():
    for name in ("neumorphism", "skeuo"):
        light, shadow = THEMES[name]["relief"]
        assert _solid(light) and _solid(shadow)
    assert THEMES["dark"]["relief"] is None


def test_glass_is_translucent_over_a_gradient():
    t = THEMES["glass"]
    assert t["surface"].startswith("rgba") and t["bg_start"] != t["bg_end"]
    assert (t["bg_start"], t["bg_end"]) == ("#101B35", "#43276B")
