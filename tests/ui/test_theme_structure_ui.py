from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QImage, QPainter
from PySide6.QtWidgets import QLabel

from app.styles.backdrop import KINDS, paint_backdrop
from app.styles.styler import WidgetStyler
from app.styles.tokens import THEMES
from app.ui.widgets.video_card import theme_radius


def _render(tokens):
    image = QImage(160, 120, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    paint_backdrop(painter, image.rect(), tokens)
    painter.end()
    return image


def test_every_backdrop_kind_paints(qtbot):
    base = dict(THEMES["dark"])
    for kind in KINDS:
        image = _render({**base, "backdrop": kind, "backdrop_colors": ("#FF0000", "#00FF00", "#0000FF", "#FFFF00")})
        assert not image.isNull() and image.pixelColor(80, 60).alpha() == 255, kind


def test_glass_backdrop_differs_from_flat(qtbot):
    flat = _render(THEMES["light"])
    glass = _render(THEMES["glass"])
    colors = {glass.pixelColor(x, y).rgb() for x in range(0, 160, 10) for y in range(0, 120, 10)}
    assert len(colors) > 12
    assert flat.pixelColor(10, 10).rgb() != glass.pixelColor(10, 10).rgb()


def test_heading_style_uppercases(qtbot):
    label = QLabel("Biblioteca")
    label.setObjectName("pageTitle")
    qtbot.addWidget(label)
    styler = WidgetStyler(THEMES["terminal"])
    styler.apply(label)
    assert label.font().capitalization() == QFont.AllUppercase
    assert label.font().letterSpacing() > 0
    styler.set_tokens(THEMES["dark"])
    styler.apply(label)
    assert label.font().capitalization() == QFont.MixedCase


def test_thumbnail_radius_follows_theme():
    assert theme_radius(10, THEMES["luxury"]) == 0
    assert theme_radius(10, THEMES["pixel"]) < theme_radius(10, THEMES["dark"])
