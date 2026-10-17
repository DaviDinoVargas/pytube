"""Tokens de design de todos os temas.

Cada tema define as mesmas chaves. Componentes consomem tokens e nunca cores soltas.
Além da paleta, um tema define o fundo (plano ou em gradiente), as superfícies da
sidebar e da barra superior (que podem ser translúcidas) e a escala de raios dos cantos.
"""

# Escala de espaçamento em múltiplos de 4
SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}

FONT_FAMILY = '"Inter", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", sans-serif'

_DEFAULT_RADIUS = {"sm": 8, "md": 12, "lg": 16}


def _theme(scheme, **tokens):
    """Completa um tema com os valores derivados quando ele não os define."""
    tokens.setdefault("bg_start", tokens["background"])
    tokens.setdefault("bg_end", tokens["background"])
    tokens.setdefault("sidebar_bg", tokens["surface"])
    tokens.setdefault("topbar_bg", tokens["surface"])
    tokens.setdefault("input_bg", tokens["background"])
    tokens.setdefault("progress", tokens["accent"])  # cor da barra de progresso do player
    tokens.setdefault("radius", _DEFAULT_RADIUS)
    tokens["scheme"] = scheme
    return tokens


DARK = _theme(
    "dark",
    background="#111318",
    surface="#191C23",
    surface_elevated="#222631",
    surface_hover="#262B38",
    text_primary="#F2F4F8",
    text_secondary="#A9B0BE",
    text_on_accent="#14111F",
    border="#303642",
    accent="#8B7CF6",
    accent_hover="#9D90F8",
    accent_soft="#2A2650",
    success="#42B883",
    warning="#E8B45A",
    error="#E06C75",
)

LIGHT = _theme(
    "light",
    background="#F6F7FB",
    surface="#FFFFFF",
    surface_elevated="#FFFFFF",
    surface_hover="#EEF0F6",
    text_primary="#171A22",
    text_secondary="#566074",
    text_on_accent="#FFFFFF",
    border="#D9DDE7",
    accent="#5B48E0",
    accent_hover="#4B39C9",
    accent_soft="#E6E2FC",
    success="#177A4D",
    warning="#9A6A0C",
    error="#C2323F",
)

# Vidro azul: fundo em gradiente, painéis translúcidos e cantos bem arredondados
OCEAN = _theme(
    "dark",
    background="#16233A",
    bg_start="#223652",
    bg_end="#0E1829",
    surface="#1B2B44",
    sidebar_bg="rgba(24, 38, 60, 215)",
    topbar_bg="rgba(24, 38, 60, 170)",
    input_bg="rgba(8, 18, 34, 140)",
    surface_elevated="#243652",
    surface_hover="rgba(120, 160, 220, 40)",
    text_primary="#EAF1FB",
    text_secondary="#A3B6D1",
    text_on_accent="#07142B",
    border="rgba(150, 180, 225, 55)",
    accent="#5B9BFF",
    accent_hover="#7DB0FF",
    accent_soft="rgba(91, 155, 255, 55)",
    success="#4FD0A0",
    warning="#EBC060",
    error="#F27F8B",
    radius={"sm": 10, "md": 14, "lg": 20},
)

# Verde profundo com cantos mais retos
FOREST = _theme(
    "dark",
    background="#0F1A15",
    surface="#15231C",
    surface_elevated="#1D2F26",
    surface_hover="#223629",
    text_primary="#EAF4EE",
    text_secondary="#9DB5A7",
    text_on_accent="#06210F",
    border="#2A3D32",
    accent="#4ADE80",
    accent_hover="#6CE89A",
    accent_soft="#1B3A29",
    success="#4ADE80",
    warning="#E8B45A",
    error="#EE7A7A",
    radius={"sm": 5, "md": 8, "lg": 12},
)

# Tons quentes sobre fundo escuro avermelhado
SUNSET = _theme(
    "dark",
    background="#1A1214",
    bg_start="#241618",
    bg_end="#150E12",
    surface="#241719",
    surface_elevated="#2F1F21",
    surface_hover="#3A2628",
    text_primary="#F8EEE9",
    text_secondary="#C2A9A2",
    text_on_accent="#2A1204",
    border="#43302F",
    accent="#F59E5B",
    accent_hover="#F8B07A",
    accent_soft="#4A2C1D",
    success="#6CCB8E",
    warning="#F2C14E",
    error="#F0848A",
    radius={"sm": 10, "md": 14, "lg": 18},
)

THEMES = {
    "dark": DARK,
    "light": LIGHT,
    "ocean": OCEAN,
    "forest": FOREST,
    "sunset": SUNSET,
}

# Preferências aceitas: os temas acima mais 'system' (segue o sistema operacional)
THEME_CHOICES = ("system",) + tuple(THEMES)
DEFAULT_THEME = "dark"
