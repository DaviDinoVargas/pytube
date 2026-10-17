from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication

from app.styles.tokens import DEFAULT_THEME, FONT_FAMILY, THEMES


def resolve_theme(preference):
    """Converte 'system' em 'dark' ou 'light' de acordo com o sistema."""
    if preference in THEMES:
        return preference
    scheme = QGuiApplication.styleHints().colorScheme()
    return "light" if scheme == Qt.ColorScheme.Light else "dark"


def build_stylesheet(t):
    r = t['radius']
    gradient = (
        f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {t['bg_start']}, stop:1 {t['bg_end']})"
    )
    return f"""
* {{ font-family: {FONT_FAMILY}; font-size: 13px; color: {t['text_primary']}; }}
QMainWindow, QWidget#root {{ background: {gradient}; }}
QStackedWidget, QScrollArea#pageScroll, QWidget#pageContent {{ background: transparent; border: none; }}
QLabel {{ background: transparent; }}

QFrame#sidebar {{ background: {t['sidebar_bg']}; border-right: 1px solid {t['border']}; }}
QFrame#topbar {{ background: {t['topbar_bg']}; border-bottom: 1px solid {t['border']}; }}
QFrame#footer {{ background: transparent; }}

QLabel#brand {{ font-size: 17px; font-weight: 700; letter-spacing: 0.3px; }}
QLabel#pageTitle {{ font-size: 24px; font-weight: 700; }}
QLabel#pageSubtitle {{ color: {t['text_secondary']}; font-size: 14px; }}
QLabel#emptyTitle {{ font-size: 17px; font-weight: 600; }}
QLabel#emptyBody {{ color: {t['text_secondary']}; font-size: 14px; }}
QLabel#groupTitle {{ font-size: 12px; font-weight: 600; color: {t['text_secondary']}; text-transform: uppercase; }}
QLabel#fieldLabel {{ color: {t['text_primary']}; font-size: 14px; }}
QLabel#statusOk {{ color: {t['success']}; }}
QLabel#statusError {{ color: {t['error']}; }}

QToolButton#navItem {{
    background: transparent; border: none; border-radius: {r['sm']}px;
    padding: 9px 12px; text-align: left; color: {t['text_secondary']}; font-weight: 500;
}}
QToolButton#navItem:hover {{ background: {t['surface_hover']}; color: {t['text_primary']}; }}
QToolButton#navItem:checked {{ background: {t['accent_soft']}; color: {t['text_primary']}; font-weight: 600; }}
QToolButton#navItem:focus {{ border: 2px solid {t['accent']}; padding: 7px 10px; }}

QToolButton#iconButton {{
    background: transparent; border: none; border-radius: {r['sm']}px; padding: 6px;
}}
QToolButton#iconButton::menu-indicator {{ image: none; width: 0px; }}
QToolButton#iconButton:hover {{ background: {t['surface_hover']}; }}
QToolButton#iconButton:checked {{ background: {t['accent_soft']}; }}
QToolButton#iconButton:focus {{ border: 2px solid {t['accent']}; padding: 4px; }}

QPushButton#primary {{
    background: {t['accent']}; color: {t['text_on_accent']}; border: none;
    border-radius: {r['sm']}px; padding: 9px 18px; font-weight: 600;
}}
QPushButton#primary:hover {{ background: {t['accent_hover']}; }}
QPushButton#primary:focus {{ border: 2px solid {t['text_primary']}; padding: 7px 16px; }}
QPushButton#primary:disabled {{ background: {t['surface_elevated']}; color: {t['text_secondary']}; }}

QLineEdit {{
    background: {t['input_bg']}; border: 1px solid {t['border']}; border-radius: {r['sm']}px;
    padding: 9px 12px; selection-background-color: {t['accent']}; selection-color: {t['text_on_accent']};
}}
QLineEdit:hover {{ border-color: {t['text_secondary']}; }}
QLineEdit:focus {{ border: 2px solid {t['accent']}; padding: 8px 11px; }}
QLineEdit[invalid="true"] {{ border: 2px solid {t['error']}; padding: 8px 11px; }}

QComboBox {{
    background: {t['surface_elevated']}; border: 1px solid {t['border']}; border-radius: {r['sm']}px;
    padding: 8px 12px; min-width: 150px;
}}
QComboBox:hover {{ border-color: {t['text_secondary']}; }}
QComboBox:focus {{ border: 2px solid {t['accent']}; padding: 7px 11px; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {t['surface_elevated']}; border: 1px solid {t['border']};
    selection-background-color: {t['accent_soft']}; selection-color: {t['text_primary']}; outline: none;
}}

QFrame#card {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: {r['md']}px; }}
QFrame#separator {{ background: {t['border']}; max-height: 1px; min-height: 1px; border: none; }}

QDialog {{ background: {t['surface']}; }}

QFrame#videoCard {{
    background: {t['surface']}; border: 2px solid {t['border']}; border-radius: {r['md']}px;
}}
QFrame#videoCard:hover {{ border-color: {t['text_secondary']}; }}
QFrame#videoCard:focus {{ border: 2px solid {t['text_primary']}; }}
QFrame#videoCard[state="downloaded"] {{ border: 2px solid {t['accent']}; background: {t['accent_soft']}; }}
QFrame#videoCard[state="missing"], QFrame#videoCard[state="invalid"] {{ border: 2px solid {t['warning']}; }}
QFrame#videoCard[state="failed"] {{ border: 2px solid {t['error']}; }}
QFrame#videoCard QLabel {{ background: transparent; }}
QFrame#videoCard QWidget {{ background: transparent; }}
QFrame#videoRow {{ background: {t['surface']}; border: 2px solid {t['border']}; border-radius: {r['md']}px; }}
QFrame#videoRow:hover {{ border-color: {t['text_secondary']}; }}
QFrame#videoRow:focus {{ border-color: {t['text_primary']}; }}
QFrame#videoRow[state="downloaded"] {{ border-color: {t['accent']}; background: {t['accent_soft']}; }}
QFrame#videoRow[state="missing"], QFrame#videoRow[state="invalid"] {{ border-color: {t['warning']}; }}
QFrame#videoRow[state="failed"] {{ border-color: {t['error']}; }}
QFrame#videoRow QLabel, QFrame#videoRow QWidget {{ background: transparent; }}
QLabel#rowState {{ font-size: 12px; font-weight: 700; padding: 2px 9px; border-radius: 9px; background: {t['surface_elevated']}; }}
QLabel#rowState[state="downloaded"] {{ background: {t['accent']}; color: {t['text_on_accent']}; }}
QLabel#rowState[state="missing"], QLabel#rowState[state="invalid"] {{ background: {t['warning']}; color: #1B1B1B; }}
QLabel#rowState[state="failed"] {{ background: {t['error']}; color: #1B1B1B; }}
QLabel#categoryChip {{ font-size: 11px; color: {t['text_secondary']}; border: 1px solid {t['border']}; border-radius: 9px; padding: 0 7px; }}
QCheckBox#cardCheck::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 2px solid #FFFFFF; background: rgba(0, 0, 0, 120); }}
QCheckBox#cardCheck::indicator:checked {{ background: {t['accent']}; border-color: {t['accent']}; }}
QLabel#cardTitle {{ font-weight: 600; font-size: 14px; }}
QLabel#cardMeta {{ color: {t['text_secondary']}; font-size: 12px; }}
QLabel#badge {{
    background: rgba(0, 0, 0, 190); color: #FFFFFF; border-radius: 6px; padding: 2px 6px;
    font-size: 12px; font-weight: 600;
}}
QFrame#stateBadge {{ border-radius: 9px; background: rgba(0, 0, 0, 190); }}
QFrame#stateBadge QLabel {{ color: #FFFFFF; font-size: 12px; font-weight: 700; background: transparent; }}
QFrame#stateBadge[state="downloaded"] {{ background: {t['accent']}; }}
QFrame#stateBadge[state="downloaded"] QLabel {{ color: {t['text_on_accent']}; }}
QFrame#stateBadge[state="missing"], QFrame#stateBadge[state="invalid"] {{ background: {t['warning']}; }}
QFrame#stateBadge[state="failed"] {{ background: {t['error']}; }}
QFrame#stateBadge[state="missing"] QLabel, QFrame#stateBadge[state="invalid"] QLabel,
QFrame#stateBadge[state="failed"] QLabel {{ color: #1B1B1B; }}

QProgressBar {{ background: {t['border']}; border: none; border-radius: 4px; }}
QProgressBar::chunk {{ background: {t['accent']}; border-radius: 4px; }}
QProgressBar[state="done"]::chunk {{ background: {t['success']}; }}
QProgressBar[state="failed"]::chunk {{ background: {t['error']}; }}

QFrame#playerWidget {{ background: #000000; border-radius: 14px; }}
QStackedWidget#playerStack {{ background: #000000; border-top-left-radius: 14px; border-top-right-radius: 14px; }}
QFrame#playerMessage {{ background: #000000; }}
QLabel#playerMessageText {{ color: #FFFFFF; font-size: 14px; background: transparent; }}
QFrame#playerControls {{ background: {t['surface_elevated']}; border-bottom-left-radius: 14px; border-bottom-right-radius: 14px; }}
QFrame#playerNotice {{ background: {t['accent_soft']}; }}
QLabel#playerTime {{ color: {t['text_secondary']}; font-size: 12px; }}
QLabel#sourceChip {{
    color: {t['text_secondary']}; border: 1px solid {t['border']}; border-radius: 9px; padding: 1px 8px; font-size: 11px; font-weight: 600;
}}
QLabel#sourceChip[source="local"] {{ color: {t['text_on_accent']}; background: {t['accent']}; border-color: {t['accent']}; }}
QToolButton#playerButton, QToolButton#playerMenuButton {{
    background: transparent; border: none; border-radius: {r['sm']}px; padding: 5px; color: {t['text_primary']}; font-weight: 600;
}}
QToolButton#playerMenuButton {{ padding: 5px 9px; }}
QToolButton#playerButton:hover, QToolButton#playerMenuButton:hover {{ background: {t['surface_hover']}; }}
QToolButton#playerButton:focus, QToolButton#playerMenuButton:focus {{ border: 2px solid {t['accent']}; padding: 3px; }}
QToolButton#playerMenuButton::menu-indicator {{ image: none; width: 0px; }}
QSlider::groove:horizontal {{ height: 6px; background: {t['border']}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {t['progress']}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {t['text_primary']}; width: 12px; height: 12px; margin: -3px 0; border-radius: 6px; }}
QSlider::handle:horizontal:hover {{ background: {t['progress']}; }}
QMenu {{ background: {t['surface_elevated']}; border: 1px solid {t['border']}; border-radius: {r['sm']}px; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {t['accent_soft']}; }}
QMenu::item:disabled {{ color: {t['text_secondary']}; }}

QFrame#filterPanel {{ background: {t['surface_elevated']}; border: 1px solid {t['border']}; border-radius: {r['md']}px; }}
QFrame#filterPanel QLabel, QFrame#filterPanel QCheckBox {{ background: transparent; }}
QToolButton#chip {{
    background: {t['accent_soft']}; color: {t['text_primary']}; border: 1px solid {t['accent']};
    border-radius: 13px; padding: 4px 12px; font-size: 12px; font-weight: 600;
}}
QToolButton#chip:hover {{ background: {t['surface_hover']}; }}
QToolButton#chip:focus {{ border: 2px solid {t['text_primary']}; }}
QToolButton#toolbarToggle {{
    background: transparent; border: 1px solid {t['border']}; border-radius: {r['sm']}px; padding: 5px 8px;
}}
QToolButton#toolbarToggle:checked {{ background: {t['accent_soft']}; border-color: {t['accent']}; }}
QToolButton#toolbarToggle:hover {{ background: {t['surface_hover']}; }}
QFrame#bulkBar {{ background: {t['accent_soft']}; border: 1px solid {t['accent']}; border-radius: {r['md']}px; }}
QFrame#bulkBar QLabel {{ background: transparent; font-weight: 600; }}

QFrame#collectionCard {{ background: {t['surface']}; border: 2px solid {t['border']}; border-radius: {r['md']}px; }}
QFrame#collectionCard:hover {{ border-color: {t['text_secondary']}; }}
QFrame#collectionCard:focus {{ border-color: {t['text_primary']}; }}
QFrame#collectionCard QLabel, QFrame#collectionCard QWidget {{ background: transparent; }}

QLabel#sectionTitle {{ font-size: 17px; font-weight: 700; }}
QLabel#watchTitle {{ font-size: 21px; font-weight: 700; }}
QToolButton#textButton {{
    background: transparent; border: none; color: {t['text_secondary']}; padding: 4px 8px; border-radius: {r['sm']}px;
}}
QToolButton#textButton:hover {{ background: {t['surface_hover']}; color: {t['text_primary']}; }}
QPushButton#linkButton {{ background: transparent; border: none; color: {t['accent']}; font-weight: 600; padding: 2px 0; }}
QPushButton#linkButton:hover {{ color: {t['accent_hover']}; }}
QPushButton#secondary {{
    background: transparent; color: {t['text_primary']}; border: 1px solid {t['border']};
    border-radius: {r['sm']}px; padding: 8px 16px; font-weight: 500;
}}
QPushButton#secondary:hover {{ background: {t['surface_hover']}; }}
QPushButton#secondary:focus {{ border: 2px solid {t['accent']}; padding: 7px 15px; }}
QPushButton#secondary:disabled {{ color: {t['text_secondary']}; }}

QRadioButton, QCheckBox {{ spacing: 10px; font-weight: 600; min-height: 24px; }}
QRadioButton::indicator, QCheckBox::indicator {{
    width: 14px; height: 14px; border: 2px solid {t['text_secondary']}; background: transparent;
}}
QRadioButton::indicator {{ border-radius: 9px; }}
QCheckBox::indicator {{ border-radius: 5px; }}
QRadioButton::indicator:checked {{
    border-color: {t['accent']};
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 {t['accent']}, stop:0.5 {t['accent']}, stop:0.55 {t['surface']}, stop:1 {t['surface']});
}}
QCheckBox::indicator:checked {{ border-color: {t['accent']}; background: {t['accent']}; }}
QRadioButton::indicator:focus, QCheckBox::indicator:focus {{ border-color: {t['text_primary']}; }}

QToolTip {{
    background: {t['surface_elevated']}; color: {t['text_primary']};
    border: 1px solid {t['border']}; padding: 5px 8px; border-radius: 6px;
}}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t['border']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {t['text_secondary']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
"""


class ThemeManager(QObject):
    theme_changed = Signal(str)

    def __init__(self, app, preference=DEFAULT_THEME):
        super().__init__()
        self._app = app
        self._preference = preference
        self._name = resolve_theme(preference)

    @property
    def name(self):
        return self._name

    @property
    def tokens(self):
        return THEMES[self._name]

    def apply(self, preference=None):
        if preference is not None:
            self._preference = preference
        self._name = resolve_theme(self._preference)
        self._app.setStyleSheet(build_stylesheet(self.tokens))
        self.theme_changed.emit(self._name)
