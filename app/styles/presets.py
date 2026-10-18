"""Estilo estrutural de cada tema (além das cores). Cada tema ganha uma personalidade própria:
fundo (backdrop), tipo de cartão, navegação, forma dos botões, densidade, títulos, sombra e brilho.

  backdrop   fundo da janela: none, orbs (vidro), aurora, sun, vignette, grid, dots, scanlines, paper, blobs, brushed, frost
  card       outline (borda), flat (sem borda), elevated (sombra), glass (vidro), hard (borda grossa + sombra seca),
             neon (borda e brilho de cor), line (só um fio), relief (luz e sombra)
  nav        pill (destaque arredondado), bar (barra de cor à esquerda), block (item invertido), underline (sublinhado)
  btn        round, pill, square
  density    escala dos espaçamentos (0.9 compacto … 1.2 arejado)
  heading    normal, upper (maiúsculas), wide (maiúsculas bem espaçadas)
  shadow     (desfoque, dx, dy, cor) dos cartões, ou None
  glow       cor do brilho do botão principal, ou None
  stroke     espessura dos ícones
  translucent  a janela inteira é translúcida (deixa ver a área de trabalho por trás)
"""

PRESETS = {
    "dark": dict(backdrop="vignette", card="outline", nav="pill", btn="round", density=1.0, heading="normal", stroke=1.75),
    "light": dict(backdrop="none", card="outline", nav="pill", btn="round", density=1.0, heading="normal", stroke=1.75),
    "ocean": dict(
        backdrop="aurora", backdrop_colors=("#2D6BD6", "#1FB6C9"), card="glass", nav="pill", btn="pill", density=1.0,
        heading="normal", shadow=(20, 0, 6, "rgba(0, 0, 0, 90)"), stroke=1.75,
    ),
    "forest": dict(backdrop="vignette", card="flat", nav="bar", btn="round", density=0.95, heading="normal", stroke=1.9),
    "sunset": dict(
        backdrop="sun", backdrop_colors=("#F2682F", "#E8438C"), card="elevated", nav="pill", btn="pill", density=1.0,
        heading="normal", shadow=(22, 0, 8, "rgba(0, 0, 0, 120)"), stroke=1.75,
    ),
    "minimal": dict(backdrop="none", card="flat", nav="underline", btn="round", density=1.15, heading="normal", stroke=1.4),
    "cinema": dict(
        backdrop="vignette", card="elevated", nav="pill", btn="pill", density=1.0, heading="normal",
        shadow=(26, 0, 10, "rgba(0, 0, 0, 190)"), stroke=1.75,
    ),
    "glass": dict(
        backdrop="orbs", backdrop_colors=("#7C4DFF", "#00B0FF", "#FF4081", "#3F51B5"), card="glass", nav="pill", btn="pill",
        density=1.05, heading="normal", shadow=(24, 0, 8, "rgba(0, 0, 0, 90)"), stroke=1.6,
    ),
    "frost": dict(
        backdrop="frost", card="glass", nav="pill", btn="pill", density=1.05, heading="normal",
        shadow=(28, 0, 10, "rgba(0, 0, 0, 80)"), stroke=1.6, translucent=True,
    ),
    "neumorphism": dict(
        backdrop="none", card="relief", nav="pill", btn="pill", density=1.15, heading="normal",
        shadow=(16, 6, 6, "rgba(163, 177, 198, 140)"), stroke=1.75,
    ),
    "nord": dict(backdrop="none", card="flat", nav="bar", btn="round", density=0.95, heading="normal", stroke=1.75),
    "dracula": dict(
        backdrop="none", card="outline", nav="pill", btn="pill", density=1.0, heading="normal", glow="#FF79C6", stroke=1.9,
    ),
    "terminal": dict(
        backdrop="scanlines", backdrop_colors=("#39FF88",), card="outline", nav="block", btn="square", density=0.9,
        heading="upper", stroke=1.6,
    ),
    "pixel": dict(
        backdrop="dots", backdrop_colors=("#45E6C1", "#FF6B9D"), card="hard", nav="block", btn="square", density=1.0,
        heading="upper", shadow=(0, 4, 4, "#0A0818"), stroke=2.2,
    ),
    "luxury": dict(backdrop="vignette", card="line", nav="bar", btn="square", density=1.2, heading="wide", stroke=1.25),
    "pastel": dict(
        backdrop="blobs", backdrop_colors=("#C4B5FD", "#A7F3D0", "#FED7AA", "#FBCFE8"), card="elevated", nav="pill",
        btn="pill", density=1.15, heading="normal", shadow=(20, 0, 6, "rgba(120, 100, 170, 60)"), stroke=1.9,
    ),
    "editorial": dict(backdrop="paper", card="line", nav="underline", btn="square", density=1.1, heading="normal", stroke=1.4),
    "fluent": dict(
        backdrop="none", card="outline", nav="bar", btn="round", density=1.0, heading="normal",
        shadow=(10, 0, 2, "rgba(0, 0, 0, 38)"), stroke=1.6,
    ),
    "cyberpunk": dict(
        backdrop="grid", backdrop_colors=("#00E5FF", "#FF2E88"), card="neon", nav="bar", btn="square", density=0.95,
        heading="upper", glow="#00E5FF", shadow=(16, 0, 0, "rgba(0, 229, 255, 80)"), stroke=1.9,
    ),
    "mono": dict(
        backdrop="none", card="hard", nav="block", btn="square", density=1.0, heading="upper",
        shadow=(0, 3, 3, "#171717"), stroke=2.0,
    ),
    "skeuo": dict(
        backdrop="brushed", card="relief", nav="pill", btn="round", density=1.0, heading="normal",
        shadow=(12, 0, 4, "rgba(0, 0, 0, 160)"), stroke=1.9,
    ),
    "earthy": dict(
        backdrop="paper", card="elevated", nav="pill", btn="pill", density=1.1, heading="normal",
        shadow=(18, 0, 5, "rgba(90, 70, 40, 55)"), stroke=1.75,
    ),
}
