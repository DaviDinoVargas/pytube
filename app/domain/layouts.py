"""Layouts: como os elementos são organizados. O tema define a aparência; o layout define a estrutura.
Qualquer layout combina com qualquer tema."""

from dataclasses import dataclass

CLASSIC, STREAMING, CINEMA, MANAGER, WORKSTATION, COMPACT = (
    "classic", "streaming", "cinema", "manager", "workstation", "compact",
)
LAYOUT_CHOICES = (CLASSIC, STREAMING, CINEMA, MANAGER, WORKSTATION, COMPACT)
DEFAULT_LAYOUT = CLASSIC

# modos da sidebar
SIDEBAR_FULL, SIDEBAR_ICONS, SIDEBAR_HIDDEN = "full", "icons", "hidden"
# organização da tela do vídeo
WATCH_STANDARD, WATCH_CINEMA, WATCH_WORKSTATION, WATCH_COMPACT = "standard", "cinema", "workstation", "compact"
# início
HOME_CATEGORIES, HOME_STREAMING = "categories", "streaming"
# barra superior
TOPBAR_FULL, TOPBAR_COMPACT = "full", "compact"


@dataclass(frozen=True)
class LayoutProfile:
    key: str
    sidebar: str = SIDEBAR_FULL  # nas páginas comuns; 'full' respeita o recolhimento escolhido pelo usuário
    sidebar_watching: str | None = None  # na tela do vídeo (None = igual a `sidebar`)
    home: str = HOME_CATEGORIES
    library_view: str | None = None  # visão padrão da biblioteca ao entrar no layout (None = a preferência do usuário)
    watch: str = WATCH_STANDARD
    landing: str = "home"  # página mostrada ao escolher o layout
    topbar: str = TOPBAR_FULL
    topbar_hidden_watching: bool = False
    details_panel: bool = False  # painel de metadados/notas à direita do player, sempre aberto
    library_list: bool = False  # lista da biblioteca à esquerda do player
    compact_window: bool = False  # janela pequena que pode ficar por cima das outras
    related: bool = True  # "Mais da sua biblioteca" abaixo do player

    def sidebar_for(self, watching):
        return (self.sidebar_watching or self.sidebar) if watching else self.sidebar


PROFILES = {
    # A. Menu lateral fixo, player central, relacionados abaixo e painel de detalhes opcional à direita
    CLASSIC: LayoutProfile(CLASSIC),
    # B. Destaque, fileiras de miniaturas, recomendações locais e coleções horizontais
    STREAMING: LayoutProfile(STREAMING, sidebar=SIDEBAR_ICONS, home=HOME_STREAMING),
    # C. Player ocupa quase toda a janela; controles e informações só quando necessário
    CINEMA: LayoutProfile(
        CINEMA, sidebar=SIDEBAR_ICONS, sidebar_watching=SIDEBAR_HIDDEN, watch=WATCH_CINEMA,
        topbar_hidden_watching=True, related=False,
    ),
    # D. Tabela de gerenciamento com filtros avançados no topo
    MANAGER: LayoutProfile(MANAGER, sidebar=SIDEBAR_ICONS, library_view="table", landing="library"),
    # E. Biblioteca à esquerda, player no centro, metadados/notas/tags à direita
    WORKSTATION: LayoutProfile(
        WORKSTATION, sidebar=SIDEBAR_ICONS, watch=WATCH_WORKSTATION, landing="watch",
        details_panel=True, library_list=True, related=False,
    ),
    # F. Janela pequena com controles essenciais, fila de reprodução e opção de ficar por cima
    COMPACT: LayoutProfile(
        COMPACT, sidebar=SIDEBAR_HIDDEN, watch=WATCH_COMPACT, landing="watch", topbar=TOPBAR_COMPACT,
        compact_window=True, related=False,
    ),
}


def profile_for(key):
    return PROFILES.get(key, PROFILES[DEFAULT_LAYOUT])
