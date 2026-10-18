"""Ajustes de estilo que o QSS não faz (o Qt ignora `text-transform`, `letter-spacing` e `box-shadow`): maiúsculas e espaçamento
dos títulos, e sombras/brilho dos cartões. Um filtro de eventos aplica tudo quando cada widget é "polido", então vale também
para o que a interface cria depois (cartões novos a cada atualização da página)."""

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QLabel, QWidget

from app.styles.colors import qcolor

HEADINGS = {
    "pageTitle", "sectionTitle", "groupTitle", "brand", "topBrand", "heroTitle", "heroKicker", "compactTitle", "emptyTitle",
}
CARDS = {
    "videoCard", "videoRow", "collectionCard", "card", "detailsPanel", "queuePanel", "workspaceDock", "filterBar", "notesIndex",
    "libraryList", "upNextRow",
}
_MARK = "_dino_effect"


def shadow_for(tokens):
    """(raio de desfoque, deslocamento x, y, cor) da sombra dos cartões do tema, ou None."""
    return tokens.get("shadow")


class WidgetStyler(QObject):
    def __init__(self, tokens):
        super().__init__()
        self._tokens = tokens

    def install(self, app=None):
        (app or QApplication.instance()).installEventFilter(self)

    def set_tokens(self, tokens):
        """Troca o tema: reaplica a todos os widgets que já existem."""
        self._tokens = tokens
        app = QApplication.instance()
        for widget in app.allWidgets():
            self.apply(widget)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Polish and isinstance(obj, QWidget):
            self.apply(obj)
        return False

    # -- aplicação --------------------------------------------------------------------------------------
    def apply(self, widget):
        name = widget.objectName()
        if name in HEADINGS and isinstance(widget, QLabel):
            self._heading(widget)
        elif name in CARDS:
            self._shadow(widget)

    def _heading(self, label):
        style = self._tokens.get("heading", "normal")
        font = QFont(label.font())
        upper = style in ("upper", "wide")
        spacing = {"upper": 1.2, "wide": 2.6}.get(style, 0.0)
        wanted = QFont.AllUppercase if upper else QFont.MixedCase
        if font.capitalization() != wanted or abs(font.letterSpacing() - spacing) > 0.01:
            font.setCapitalization(wanted)
            font.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
            label.setFont(font)

    def _shadow(self, widget):
        spec = shadow_for(self._tokens)
        existing = widget.graphicsEffect()
        if spec is None:
            if existing is not None and widget.property(_MARK):
                widget.setGraphicsEffect(None)
                widget.setProperty(_MARK, False)
            return
        blur, dx, dy, color = spec
        if existing is not None and not widget.property(_MARK):
            return  # o widget já tem um efeito próprio (ex.: esmaecer); não o substitui
        effect = existing if isinstance(existing, QGraphicsDropShadowEffect) and widget.property(_MARK) else QGraphicsDropShadowEffect(widget)
        effect.setBlurRadius(blur)
        effect.setOffset(dx, dy)
        effect.setColor(qcolor(color) if isinstance(color, str) else QColor(color))
        if effect is not existing:
            widget.setGraphicsEffect(effect)
            widget.setProperty(_MARK, True)
