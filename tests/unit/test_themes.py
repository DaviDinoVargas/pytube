import re

import pytest

from app.i18n import _STRINGS
from app.styles.tokens import THEME_CHOICES, THEMES


def _rgb(value):
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def _luminance(value):
    def channel(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in _rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _solid(value):
    return bool(re.fullmatch(r"#[0-9A-Fa-f]{6}", value))


def test_all_themes_define_same_tokens():
    keys = set(THEMES["dark"])
    for name, tokens in THEMES.items():
        assert set(tokens) == keys, name


def test_system_is_a_choice_and_not_a_theme():
    assert "system" in THEME_CHOICES and "system" not in THEMES


def test_every_theme_is_translated_in_both_languages():
    for language in _STRINGS.values():
        for name in THEME_CHOICES:
            assert f"theme.{name}" in language


@pytest.mark.parametrize("name", THEMES)
def test_text_contrast_meets_wcag_aa(name):
    t = THEMES[name]
    for surface in ("background", "bg_start", "bg_end", "surface", "surface_elevated"):
        assert contrast(t["text_primary"], t[surface]) >= 4.5, (name, "primary", surface)
        assert contrast(t["text_secondary"], t[surface]) >= 4.5, (name, "secondary", surface)
    assert contrast(t["text_on_accent"], t["accent"]) >= 4.5, (name, "on_accent")
    assert contrast(t["text_on_accent"], t["accent_hover"]) >= 4.5, (name, "on_accent_hover")


@pytest.mark.parametrize("name", THEMES)
def test_status_colors_are_readable(name):
    t = THEMES[name]
    for status in ("success", "error"):
        assert contrast(t[status], t["surface"]) >= 4.5, (name, status)
    assert contrast(t["accent"], t["background"]) >= 3, (name, "accent")


@pytest.mark.parametrize("name", THEMES)
def test_solid_tokens_are_valid_hex(name):
    t = THEMES[name]
    for key in ("background", "surface", "text_primary", "accent"):
        assert _solid(t[key])
