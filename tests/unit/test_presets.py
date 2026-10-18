from app.styles.backdrop import KINDS
from app.styles.presets import PRESETS
from app.styles.theme_manager import build_stylesheet
from app.styles.tokens import THEMES


def test_every_theme_has_a_known_structure():
    for name, t in THEMES.items():
        assert t["backdrop"] in KINDS, name
        assert t["card"] in ("outline", "flat", "elevated", "glass", "hard", "neon", "line", "relief"), name
        assert t["nav"] in ("pill", "bar", "block", "underline"), name
        assert t["btn"] in ("round", "pill", "square"), name
        assert t["heading"] in ("normal", "upper", "wide"), name
        assert 0.8 <= t["density"] <= 1.3, name


def test_themes_are_structurally_diverse():
    """Os temas não diferem só na cor: há vários tipos de fundo, cartão, navegação e botão."""
    assert len({t["backdrop"] for t in THEMES.values()}) >= 8
    assert len({t["card"] for t in THEMES.values()}) >= 6
    assert len({t["nav"] for t in THEMES.values()}) == 4
    assert len({t["btn"] for t in THEMES.values()}) == 3
    signatures = {(t["backdrop"], t["card"], t["nav"], t["btn"], t["heading"]) for t in THEMES.values()}
    assert len(signatures) >= len(THEMES) * 0.7


def test_glass_is_really_translucent():
    t = THEMES["glass"]
    assert t["card"] == "glass" and t["backdrop"] == "orbs"
    assert t["surface"].startswith("rgba")
    alpha = int(t["surface"].strip("rgba()").split(",")[-1])
    assert 0 < alpha < 200
    sheet = build_stylesheet(t)
    assert "QWidget#root { background: transparent; }" in sheet


def test_stylesheet_follows_structure():
    assert "border-left: 3px solid" in build_stylesheet(THEMES["forest"])  # nav 'bar'
    assert "border-bottom: 2px solid" in build_stylesheet(THEMES["minimal"])  # nav 'underline'
    assert "border-radius: 0px" in build_stylesheet(THEMES["terminal"])  # botões quadrados


def test_presets_only_reference_known_themes():
    assert set(PRESETS) <= set(THEMES)
