"""Layouts: como o aplicativo inteiro é organizado. O tema define a aparência; o layout define a anatomia (que navegação existe,
onde fica, o que cada página mostra). Qualquer layout combina com qualquer tema."""

from dataclasses import dataclass

CLASSIC, STREAMING, CINEMA, MANAGER, WORKSTATION, COMPACT = (
    "classic", "streaming", "cinema", "manager", "workstation", "compact",
)
LAYOUT_CHOICES = (CLASSIC, STREAMING, CINEMA, MANAGER, WORKSTATION, COMPACT)
DEFAULT_LAYOUT = CLASSIC

# navegação
NAV_SIDEBAR, NAV_ICONS, NAV_TOP, NAV_TREE, NAV_NONE = "sidebar", "icons", "top", "tree", "none"
# compatibilidade com o nome antigo dos modos da sidebar
SIDEBAR_FULL, SIDEBAR_ICONS, SIDEBAR_HIDDEN = "full", "icons", "hidden"
# barra superior (link e busca)
TOPBAR_FULL, TOPBAR_SLIM, TOPBAR_COMPACT, TOPBAR_NONE = "full", "slim", "compact", "none"
# estilo da navegação do topo
TOPNAV_STREAMING, TOPNAV_CINEMA = "streaming", "cinema"
# organização da tela do vídeo
WATCH_STANDARD, WATCH_STREAMING, WATCH_CINEMA, WATCH_WORKSTATION, WATCH_COMPACT = (
    "standard", "streaming", "cinema", "workstation", "compact",
)
# início
HOME_CATEGORIES, HOME_STREAMING, HOME_WALL = "categories", "streaming", "wall"


@dataclass(frozen=True)
class LayoutProfile:
    key: str
    nav: str = NAV_SIDEBAR  # que navegação existe nas páginas comuns
    nav_watching: str | None = None  # na tela do vídeo (None = igual a `nav`)
    topbar: str = TOPBAR_FULL
    topbar_hidden_watching: bool = False
    topnav_style: str = TOPNAV_STREAMING  # só vale com nav == 'top'
    statusbar: bool = False  # barra de estado no rodapé (contagens, espaço, downloads)
    ribbon: bool = False  # faixa de ações sobre a seleção, no topo da biblioteca
    home: str = HOME_CATEGORIES
    library_view: str | None = None  # visão da biblioteca imposta pelo layout (None = a preferência do usuário)
    page_redirects: tuple = ()  # (página, consulta): em layouts de tabela única, várias páginas viram uma consulta da biblioteca
    watch: str = WATCH_STANDARD
    landing: str = "home"
    details_panel: bool = False  # painel de metadados/notas à direita do player, sempre aberto
    library_list: bool = False  # painel esquerdo da biblioteca/fila/notas ao lado do player
    up_next: bool = False  # coluna "A seguir" (fila + relacionados) ao lado do player
    preview_pane: bool = False  # prévia do item selecionado ao lado da tabela
    compact_window: bool = False  # janela pequena que pode ficar por cima das outras
    related: bool = True  # "Mais da sua biblioteca" abaixo do player
    inline_filters: bool = False  # filtros avançados em uma barra fixa no topo da biblioteca

    # -- derivados ---------------------------------------------------------------------------
    def nav_for(self, watching):
        return (self.nav_watching or self.nav) if watching else self.nav

    def sidebar_for(self, watching):
        """Modo da sidebar para o estado atual (vale também para o 'icons', que é uma sidebar recolhida)."""
        nav = self.nav_for(watching)
        return {NAV_SIDEBAR: SIDEBAR_FULL, NAV_ICONS: SIDEBAR_ICONS}.get(nav, SIDEBAR_HIDDEN)

    def redirect(self, page):
        for source, target in self.page_redirects:
            if source == page:
                return target
        return None


PROFILES = {
    # A. Menu lateral fixo, barra de link e busca no topo, player central, relacionados abaixo e detalhes opcionais
    CLASSIC: LayoutProfile(CLASSIC),
    # B. Sem sidebar: navegação em abas no topo; destaque em tela cheia, fileiras de pôsteres; vídeo + coluna "A seguir"
    STREAMING: LayoutProfile(
        STREAMING, nav=NAV_TOP, topbar=TOPBAR_NONE, home=HOME_STREAMING, library_view="posters", watch=WATCH_STREAMING, up_next=True,
        related=False,
    ),
    # C. Sem barras: só um cabeçalho que some; início em mural de pôsteres; o player ocupa a janela
    CINEMA: LayoutProfile(
        CINEMA, nav=NAV_TOP, nav_watching=NAV_NONE, topbar=TOPBAR_NONE, topnav_style=TOPNAV_CINEMA, home=HOME_WALL,
        library_view="wall", watch=WATCH_CINEMA, related=False,
    ),
    # D. Gerenciador de arquivos: árvore à esquerda, faixa de ações, tabela, prévia à direita e barra de estado
    MANAGER: LayoutProfile(
        MANAGER, nav=NAV_TREE, topbar=TOPBAR_SLIM, statusbar=True, ribbon=True, library_view="table", landing="library",
        inline_filters=True, preview_pane=True,
        page_redirects=(("home", "library"), ("downloaded", "library"), ("continue", "library"), ("history", "library")),
    ),
    # E. Estação de trabalho (estilo IDE): barra de atividades, painéis laterais, notas com marcadores e barra de estado
    WORKSTATION: LayoutProfile(
        WORKSTATION, nav=NAV_ICONS, topbar=TOPBAR_SLIM, statusbar=True, watch=WATCH_WORKSTATION, landing="watch",
        details_panel=True, library_list=True, related=False,
    ),
    # F. Janela pequena e flutuante: cabeçalho próprio, controles essenciais e fila
    COMPACT: LayoutProfile(
        COMPACT, nav=NAV_NONE, topbar=TOPBAR_NONE, watch=WATCH_COMPACT, landing="watch", compact_window=True, related=False,
    ),
}


def profile_for(key):
    return PROFILES.get(key, PROFILES[DEFAULT_LAYOUT])
