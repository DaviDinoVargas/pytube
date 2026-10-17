"""Tokens de design de todos os temas.

Cada tema define as mesmas chaves. Componentes consomem tokens e nunca cores soltas.
Além da paleta, um tema define o fundo (plano ou em gradiente), as superfícies da
sidebar e da barra superior (que podem ser translúcidas) e a escala de raios dos cantos.
"""

# Escala de espaçamento em múltiplos de 4
SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}

FONT_FAMILY = '"Inter", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", sans-serif'

_DEFAULT_RADIUS = {"sm": 8, "md": 12, "lg": 16}

# Tokens opcionais: o tema só informa o que muda em relação ao padrão
#   accent_fg        cor do destaque quando usado como TEXTO ou ícone (links); padrão = accent
#   focus            cor do anel de foco do teclado; padrão = accent
#   downloaded_bg/_border  cores do estado 'baixado' nos cartões; padrão = accent_soft / accent
#   font / title_font      famílias de fonte do texto e dos títulos
#   border_width     espessura das bordas dos painéis e campos (Pixel Art usa 2)
#   relief           (luz, sombra): bordas em relevo, usadas por Relevo suave e Objetos físicos
#   sidebar_width    largura da sidebar expandida (fontes monoespaçadas pedem mais)
#   title_scale      multiplica o tamanho dos títulos (Editorial usa títulos grandes)
#   btn_top/btn_bottom     gradiente dos botões principais (Objetos físicos); padrão = accent (cor chapada)


def _readable_on(background):
    from app.styles.contrast import ratio

    return max(("#1B1B1B", "#FFFFFF"), key=lambda text: ratio(text, background))


def _theme(scheme, **tokens):
    """Completa um tema com os valores derivados quando ele não os define."""
    tokens.setdefault("bg_start", tokens["background"])
    tokens.setdefault("bg_end", tokens["background"])
    tokens.setdefault("sidebar_bg", tokens["surface"])
    tokens.setdefault("topbar_bg", tokens["surface"])
    tokens.setdefault("input_bg", tokens["background"])
    tokens.setdefault("progress", tokens["accent"])  # cor da barra de progresso do player
    tokens.setdefault("radius", _DEFAULT_RADIUS)
    tokens.setdefault("accent_fg", tokens["accent"])
    tokens.setdefault("focus", tokens["accent"])
    tokens.setdefault("downloaded_bg", tokens["accent_soft"])
    tokens.setdefault("downloaded_border", tokens["accent"])
    tokens.setdefault("font", FONT_FAMILY)
    tokens.setdefault("title_font", tokens["font"])
    tokens.setdefault("border_width", 1)
    tokens.setdefault("relief", None)
    tokens.setdefault("btn_top", tokens["accent"])
    tokens.setdefault("btn_bottom", tokens["accent"])
    # texto dos selos de aviso/erro: o que contrasta mais com a cor do selo (claro ou escuro)
    for status in ("warning", "error"):
        tokens.setdefault(f"text_on_{status}", _readable_on(tokens[status]))
    tokens.setdefault("text_on_downloaded", _readable_on(tokens["downloaded_border"]))
    tokens.setdefault("title_scale", 1.0)
    tokens.setdefault("sidebar_width", 232)
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
    accent="#5B9BFF", accent_fg="#6FA8FF",
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

# ---------------------------------------------------------------------------------------------
# Temas da v12. As cores base são as da proposta de cada estilo; onde a cor original não atinge
# contraste legível (WCAG AA, 4,5:1 para texto) o valor foi ajustado para o mais próximo que atinge,
# e o tema ganha um token próprio para o papel (ex.: accent_fg, text_secondary).
# ---------------------------------------------------------------------------------------------
MONO_FONTS = '"JetBrains Mono", "IBM Plex Mono", "Cascadia Mono", "Consolas", "DejaVu Sans Mono", monospace'
SERIF_FONTS = '"Playfair Display", "Georgia", "Cambria", "Times New Roman", serif'

# 1. Minimalista: claro, limpo, o vídeo é o centro
MINIMAL = _theme(
    "light",
    background="#F7F8FA", surface="#FFFFFF", surface_elevated="#FFFFFF", surface_hover="#EEF0F4",
    text_primary="#202124", text_secondary="#5F6368", text_on_accent="#FFFFFF",
    border="#E5E7EB", accent="#4263EB", accent_hover="#3651D4", accent_soft="#E7ECFD",
    success="#1B7F4B", warning="#9A6700", error="#C62828",
    radius={"sm": 8, "md": 10, "lg": 12},
)

# 2. Cinema: imersão; destaque lilás e progresso do vídeo em rosa
CINEMA = _theme(
    "dark",
    background="#101114", surface="#191A20", surface_elevated="#22232B", surface_hover="#2A2B35",
    text_primary="#F5F5F5", text_secondary="#A3A5B2", text_on_accent="#1A0F2E",
    border="#2E2F3A", accent="#B388FF", accent_hover="#C5A3FF", accent_soft="#2D2347",
    success="#5BD38D", warning="#EDBB5C", error="#FF7A8A", progress="#FF375F",
    radius={"sm": 10, "md": 13, "lg": 16},
)

# 3. Vidro fosco: gradiente, painéis translúcidos (o Qt não desfoca widgets; a sensação vem da translucidez)
GLASS = _theme(
    "dark",
    background="#16204A", bg_start="#101B35", bg_end="#43276B",
    surface="rgba(255, 255, 255, 26)", sidebar_bg="rgba(255, 255, 255, 26)", topbar_bg="rgba(255, 255, 255, 20)",
    input_bg="rgba(255, 255, 255, 20)", surface_elevated="#2B2F63", surface_hover="rgba(255, 255, 255, 46)",
    text_primary="#F8FAFC", text_secondary="#DCE4F1", text_on_accent="#06222E",
    border="rgba(255, 255, 255, 56)", accent="#80D8FF", accent_hover="#A6E5FF", accent_soft="rgba(128, 216, 255, 48)",
    success="#6EE7B7", warning="#FCD34D", error="#FCA5A5",
    radius={"sm": 12, "md": 16, "lg": 22},
)

# 4. Relevo suave: tudo da mesma cor, formas separadas por luz e sombra
NEUMORPHISM = _theme(
    "light",
    background="#E9EDF2", surface="#E9EDF2", surface_elevated="#EEF1F6", surface_hover="#DFE4EC",
    text_primary="#293241", text_secondary="#556070", text_on_accent="#0A0F1E",
    border="#CBD3DF", accent="#607DCC", accent_hover="#7490D8", accent_soft="#D9E1F4",
    accent_fg="#3C57A8", downloaded_border="#4A67B8", focus="#3C57A8",
    success="#17703F", warning="#8F5F00", error="#B3261E",
    radius={"sm": 14, "md": 18, "lg": 22},
    relief=("#FFFFFF", "#C2CAD7"),
)

# 5. Nord: frio e discreto
NORD = _theme(
    "dark",
    background="#2E3440", surface="#3B4252", surface_elevated="#434C5E", surface_hover="#4C566A",
    text_primary="#ECEFF4", text_secondary="#C9D1DE", text_on_accent="#2E3440",
    border="#4C566A", accent="#88C0D0", accent_hover="#9FD0DE", accent_soft="#3F5560",
    success="#B1CB9A", warning="#EBCB8B", error="#F4B0B5", progress="#B48EAD",
    accent_fg="#98CCDA", downloaded_bg="#434F45", downloaded_border="#A3BE8C",
    radius={"sm": 6, "md": 8, "lg": 12},
)

# 6. Dracula: escuro vibrante; rosa e ciano em ações e indicadores
DRACULA = _theme(
    "dark",
    background="#282A36", surface="#343746", surface_elevated="#3D4152", surface_hover="#464A5E",
    text_primary="#F8F8F2", text_secondary="#C0C4D9", text_on_accent="#1E1F29",
    border="#4A4E66", accent="#BD93F9", accent_hover="#CCABFB", accent_soft="#44385F",
    success="#50FA7B", warning="#F1FA8C", error="#FF9A9A", progress="#FF79C6",
    focus="#8BE9FD", accent_fg="#CFB0FB", downloaded_bg="#2F4A45", downloaded_border="#50FA7B",
    radius={"sm": 8, "md": 12, "lg": 14},
)

# 7. Terminal: verde sobre quase preto, fonte monoespaçada, cantos retos
TERMINAL = _theme(
    "dark",
    background="#080D0A", surface="#101A13", surface_elevated="#16231A", surface_hover="#1C2D21",
    text_primary="#C6F6D5", text_secondary="#75A987", text_on_accent="#04140A",
    border="#25402D", accent="#39FF88", accent_hover="#6BFFA6", accent_soft="#12361F",
    success="#39FF88", warning="#E6D35A", error="#FF7B72",
    font=MONO_FONTS, sidebar_width=280, radius={"sm": 2, "md": 3, "lg": 4},
)

# 8. Pixel Art: bordas sólidas de 2 px, cantos quadrados
PIXEL = _theme(
    "dark",
    background="#17152B", surface="#282449", surface_elevated="#312C5A", surface_hover="#3B3570",
    text_primary="#FFF4D6", text_secondary="#C4BCE0", text_on_accent="#06241D",
    border="#5B54A0", accent="#45E6C1", accent_hover="#7AF0D6", accent_soft="#1F4A5A",
    success="#7BEA8A", warning="#FFD166", error="#FF7C9F", progress="#FF6B9D",
    font=MONO_FONTS, sidebar_width=280, border_width=2, radius={"sm": 0, "md": 0, "lg": 0},
)

# 9. Luxo: dourado só nos detalhes, títulos com serifa
LUXURY = _theme(
    "dark",
    background="#121212", surface="#202020", surface_elevated="#2A2A2A", surface_hover="#333333",
    text_primary="#F3EEE5", text_secondary="#ABA59F", text_on_accent="#1A1408",
    border="#3A3733", accent="#C9A96E", accent_hover="#D9BC86", accent_soft="#3A3224",
    success="#8DC9A0", warning="#D9B45F", error="#E58C86",
    title_font=SERIF_FONTS, title_scale=1.1, radius={"sm": 4, "md": 6, "lg": 8},
)

# 10. Pastel: lavanda, menta e pêssego sobre fundo lilás clarinho
PASTEL = _theme(
    "light",
    background="#FAF7FF", surface="#FFFFFF", surface_elevated="#FFFFFF", surface_hover="#F1ECFB",
    text_primary="#302B3A", text_secondary="#665F75", text_on_accent="#2A1F55",
    border="#E6DEF5", accent="#C4B5FD", accent_hover="#B09CFB", accent_soft="#EDE8FD",
    accent_fg="#6B4FD1", focus="#6B4FD1",
    progress="#6B4FD1", success="#1F7A55", warning="#946200", error="#C0392B",
    downloaded_bg="#DDF8EC", downloaded_border="#6CCBA2",
    radius={"sm": 12, "md": 16, "lg": 22},
)

# 11. Editorial: papel, títulos com serifa
EDITORIAL = _theme(
    "light",
    background="#F4F0E8", surface="#FFFCF6", surface_elevated="#FFFCF6", surface_hover="#EFE9DD",
    text_primary="#242424", text_secondary="#625A50", text_on_accent="#FFFFFF",
    border="#D9D1C5", accent="#B84A36", accent_hover="#A13F2D", accent_soft="#F3DFD8",
    success="#2F7A46", warning="#8F5B00", error="#B3261E",
    title_font=SERIF_FONTS, title_scale=1.3, radius={"sm": 2, "md": 4, "lg": 6},
)

# 12. Fluent: Windows 11 (Segoe UI, cantos de 4 e 8 px)
FLUENT = _theme(
    "light",
    background="#F3F3F3", surface="#FFFFFF", surface_elevated="#FFFFFF", surface_hover="#F0F0F0",
    text_primary="#1A1A1A", text_secondary="#5D5D5D", text_on_accent="#FFFFFF",
    border="#E0E0E0", accent="#0F6CBD", accent_hover="#115EA3", accent_soft="#DCEBFA",
    success="#0F7B0F", warning="#835B00", error="#C42B1C",
    font='"Segoe UI Variable Text", "Segoe UI", "Noto Sans", sans-serif',
    radius={"sm": 4, "md": 8, "lg": 8},
)

# 13. Cyberpunk: neon discreto; ciano nas ações, magenta nos detalhes
CYBERPUNK = _theme(
    "dark",
    background="#090B18", surface="#15172B", surface_elevated="#1D2040", surface_hover="#262A52",
    text_primary="#E8F1FF", text_secondary="#97A3C4", text_on_accent="#001418",
    border="#2B3566", accent="#00E5FF", accent_hover="#5CF0FF", accent_soft="#0E3A4A",
    success="#2EE6A6", warning="#FFC247", error="#FF6B94", progress="#FF2E88",
    focus="#FF2E88", radius={"sm": 6, "md": 8, "lg": 10},
)

# 14. Monocromático: a hierarquia vem do espaçamento e do peso do texto
MONO = _theme(
    "light",
    background="#F5F5F5", surface="#FFFFFF", surface_elevated="#FFFFFF", surface_hover="#EBEBEB",
    text_primary="#171717", text_secondary="#5E5E5E", text_on_accent="#FFFFFF",
    border="#D4D4D4", accent="#171717", accent_hover="#404040", accent_soft="#E5E5E5",
    success="#157F3D", warning="#8A5A00", error="#B91C1C",
    radius={"sm": 6, "md": 8, "lg": 10},
)

# 15. Objetos físicos: aço escovado, botões com relevo (a cor metálica fica nos botões)
SKEUO = _theme(
    "dark",
    background="#30343B", surface="#3A3F47", surface_elevated="#454B54", surface_hover="#505762",
    text_primary="#F4F4F5", text_secondary="#CAD0D8", text_on_accent="#0A1A26",
    border="#1E2126", accent="#4EA5D9", accent_hover="#6FB8E4", accent_soft="#244A63",
    success="#6FD39A", warning="#EDB95E", error="#FFA8A0",
    accent_fg="#8CC8F0", btn_top="#C7CED6", btn_bottom="#9AA3AD", relief=("#5A616C", "#16181C"),
    radius={"sm": 6, "md": 8, "lg": 12},
)

# 16. Terra: tons naturais; terracota, oliva e marrom
EARTHY = _theme(
    "light",
    background="#F2EEE6", surface="#FFFCF5", surface_elevated="#FFFCF5", surface_hover="#EBE5D8",
    text_primary="#302F29", text_secondary="#6B5744", text_on_accent="#2A1208",
    border="#DDD5C6", accent="#C76D4B", accent_hover="#D4805F", accent_soft="#F5E1D6",
    accent_fg="#A5532F", focus="#A5532F",
    success="#53662F", warning="#8A5A00", error="#B3261E", progress="#75815C",
    downloaded_bg="#E6EAD8", downloaded_border="#667250",
    radius={"sm": 8, "md": 12, "lg": 16},
)

THEMES = {
    "dark": DARK,
    "light": LIGHT,
    "ocean": OCEAN,
    "forest": FOREST,
    "sunset": SUNSET,
    "minimal": MINIMAL,
    "cinema": CINEMA,
    "glass": GLASS,
    "neumorphism": NEUMORPHISM,
    "nord": NORD,
    "dracula": DRACULA,
    "terminal": TERMINAL,
    "pixel": PIXEL,
    "luxury": LUXURY,
    "pastel": PASTEL,
    "editorial": EDITORIAL,
    "fluent": FLUENT,
    "cyberpunk": CYBERPUNK,
    "mono": MONO,
    "skeuo": SKEUO,
    "earthy": EARTHY,
}

# Preferências aceitas: os temas acima mais 'system' (segue o sistema operacional)
THEME_CHOICES = ("system",) + tuple(THEMES)
DEFAULT_THEME = "dark"
