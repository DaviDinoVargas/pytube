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
QStackedWidget {{ background: transparent; }}
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
