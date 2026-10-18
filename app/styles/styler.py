"""Ajustes de estilo que o QSS não faz (o Qt ignora `text-transform`, `letter-spacing` e `box-shadow`): maiúsculas e espaçamento
dos títulos, e sombras/brilho dos cartões."""

from PySide6.QtCore import QObject
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
    """Aplica o que o QSS não faz. NÃO usa filtro de eventos do aplicativo: um filtro em Python recebendo todos os eventos
    derrubava o processo quando o QtWebEngine (player online) criava e destruía seus objetos internos. Em vez disso o
    tema varre as janelas (`sweep`) ao trocar de tema, de página e em intervalos curtos enquanto há algo a aplicar."""

    def __init__(self, tokens):
        super().__init__()
        self._tokens = tokens

    @property
    def active(self):
        """O tema atual pede algo além do QSS (títulos em maiúsculas, sombras ou brilho)?"""
        t = self._tokens
        return t.get("heading", "normal") != "normal" or bool(t.get("shadow")) or bool(t.get("glow"))

    def set_tokens(self, tokens):
        """Troca o tema: reaplica a tudo o que já existe (inclusive para desfazer o efeito do tema anterior)."""
        self._tokens = tokens
        self.sweep()

    def sweep(self, root=None):
        roots = [root] if root is not None else QApplication.instance().topLevelWidgets()
        for top in roots:
            self.apply(top)
            for widget in top.findChildren(QWidget):
                self.apply(widget)

    # -- aplicação --------------------------------------------------------------------------------------
    def apply(self, widget):
        name = widget.objectName()
        if name in HEADINGS and isinstance(widget, QLabel):
            self._heading(widget)
        elif name in CARDS:
            self._shadow(widget, shadow_for(self._tokens))
        elif name == "primary":
            glow = self._tokens.get("glow")
            self._shadow(widget, (18, 0, 0, glow) if glow else None)

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

    def _shadow(self, widget, spec):
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
        wanted = qcolor(color) if isinstance(color, str) else QColor(color)
        if effect is existing and effect.blurRadius() == blur and effect.offset().x() == dx and effect.offset().y() == dy \
                and effect.color() == wanted:
            return  # já está como o tema pede: nada de repintar a cada varredura
        effect.setBlurRadius(blur)
        effect.setOffset(dx, dy)
        effect.setColor(wanted)
        if effect is not existing:
            widget.setGraphicsEffect(effect)
            widget.setProperty(_MARK, True)


def shared_styler(tokens, app=None):
    """Um único WidgetStyler por aplicação: quem pede depois só atualiza os tokens do que já existe."""
    app = app or QApplication.instance()
    styler = getattr(app, "_dino_styler", None)
    if styler is None:
        styler = WidgetStyler(tokens)
        app._dino_styler = styler
    return styler
