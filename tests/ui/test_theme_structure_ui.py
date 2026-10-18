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


def test_sweep_styles_widgets_created_later_and_reverts_on_theme_change(qtbot):
    from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect

    root = QFrame()
    qtbot.addWidget(root)
    card = QFrame(root)
    card.setObjectName("videoCard")
    title = QLabel("Início", root)
    title.setObjectName("pageTitle")
    styler = WidgetStyler(THEMES["pixel"])
    assert styler.active
    styler.sweep(root)
    assert isinstance(card.graphicsEffect(), QGraphicsDropShadowEffect)
    assert title.font().capitalization() == QFont.AllUppercase
    effect = card.graphicsEffect()
    styler.sweep(root)
    assert card.graphicsEffect() is effect  # varreduras seguidas não recriam nem repintam o efeito
    styler.set_tokens(THEMES["light"])
    styler.sweep(root)
    assert not styler.active and card.graphicsEffect() is None
    assert title.font().capitalization() == QFont.MixedCase


def test_no_application_wide_python_event_filter(qtbot):
    """Um filtro de eventos do aplicativo em Python derrubava o processo com o QtWebEngine."""
    import app.styles.styler as styler_module

    assert "eventFilter" not in vars(styler_module.WidgetStyler)
