"""Contraste entre cores dos temas (WCAG). Aceita '#RRGGBB' e 'rgba(r, g, b, a)' (a de 0 a 255)."""

import re

_RGBA = re.compile(r"rgba\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)")


def parse(color):
    """Devolve (r, g, b, alpha) com alpha entre 0 e 1."""
    color = color.strip()
    match = _RGBA.fullmatch(color)
    if match:
        r, g, b, a = (float(x) for x in match.groups())
        return r, g, b, a / 255
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16), 1.0
    raise ValueError(f"cor inválida: {color!r}")


def flatten(color, under):
    """Cor opaca resultante de `color` desenhada sobre `under` (que também pode ser translúcida: usa o fundo preto)."""
    r, g, b, a = parse(color)
    if a >= 1:
        return r, g, b
    ur, ug, ub = flatten(under, "#000000") if parse(under)[3] < 1 else parse(under)[:3]
    return r * a + ur * (1 - a), g * a + ug * (1 - a), b * a + ub * (1 - a)


def luminance(rgb):
    def channel(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(foreground, background, under="#000000"):
    """Razão de contraste entre duas cores. O fundo translúcido é composto sobre `under`."""
    fg = flatten(foreground, flatten_hex(background, under))
    bg = flatten(background, under)
    hi, lo = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def flatten_hex(color, under):
    r, g, b = flatten(color, under)
    return "#{:02X}{:02X}{:02X}".format(round(r), round(g), round(b))
