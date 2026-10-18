import re

import pytest

from app.styles.theme_manager import build_stylesheet
from app.styles.tokens import THEMES


@pytest.mark.parametrize("name", THEMES)
def test_every_theme_builds_a_complete_stylesheet(name):
    sheet = build_stylesheet(THEMES[name])
    assert "{t[" not in sheet and "{r[" not in sheet and "None" not in sheet
    assert not re.search(r"\{[a-z_]+\(", sheet)  # nenhum trecho de f-string ficou sem avaliar
    assert sheet.count("{") == sheet.count("}")
    assert THEMES[name]["font"].split(",")[0] in sheet


def test_pixel_art_uses_two_pixel_square_borders_and_thicker_focus():
    sheet = build_stylesheet(THEMES["pixel"])
    assert "QFrame#card { background: rgba" not in sheet
    assert re.search(r"QFrame#card \{[^}]*border: 3px solid #FFF4D6; border-radius: 0px", sheet)
    assert re.search(r"QLineEdit:focus \{ border: 3px solid", sheet)


def test_terminal_uses_monospace_everywhere_and_serif_only_in_titles():
    assert "* { font-family: " + THEMES["terminal"]["font"] in build_stylesheet(THEMES["terminal"])
    luxury = build_stylesheet(THEMES["luxury"])
    assert "Playfair Display" in luxury and re.search(r"QLabel#pageTitle \{ font-family: \"Playfair", luxury)
    assert "* { font-family: " + THEMES["luxury"]["font"] in luxury


def test_editorial_titles_are_larger_than_the_default():
    default = re.search(r"QLabel#pageTitle \{[^}]*font-size: (\d+)px", build_stylesheet(THEMES["dark"])).group(1)
    editorial = re.search(r"QLabel#pageTitle \{[^}]*font-size: (\d+)px", build_stylesheet(THEMES["editorial"])).group(1)
    assert int(editorial) > int(default)


def test_relief_themes_draw_light_and_shadow_edges():
    for name in ("neumorphism", "skeuo"):
        light, shadow = THEMES[name]["relief"]
        sheet = build_stylesheet(THEMES[name])
        assert f"border-top-color: {light}" in sheet and f"border-bottom-color: {shadow}" in sheet
    assert "border-top-color" not in build_stylesheet(THEMES["dark"])


def test_skeuomorphic_buttons_use_a_vertical_gradient_and_invert_when_pressed():
    sheet = build_stylesheet(THEMES["skeuo"])
    assert re.search(r"QPushButton#primary \{ background: qlineargradient\(x1:0, y1:0, x2:0, y2:1, stop:0 #C7CED6, stop:1 #9AA3AD", sheet) or \
        "stop:0 #C7CED6, stop:1 #9AA3AD" in sheet
    assert "QPushButton#primary:pressed { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #9AA3AD, stop:1 #C7CED6" in sheet


def test_pastel_uses_the_dark_lavender_for_links_and_mint_for_downloaded():
    t = THEMES["pastel"]
    sheet = build_stylesheet(t)
    assert f"QPushButton#linkButton {{ background: transparent; border: none; color: {t['accent_fg']}" in sheet
    assert t["downloaded_bg"] in sheet and t["accent_fg"] != t["accent"]


def test_focus_ring_uses_the_focus_token():
    t = THEMES["dracula"]
    assert f"QToolButton#navItem:focus {{ border: 2px solid {t['focus']}" in build_stylesheet(t)
    assert t["focus"] != t["accent"]
