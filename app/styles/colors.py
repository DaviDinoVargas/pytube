from PySide6.QtGui import QColor


def qcolor(value):
    """'#RRGGBB' ou 'rgba(r, g, b, a)' (a de 0 a 255) em QColor."""
    value = value.strip()
    if value.startswith("rgba"):
        r, g, b, a = [int(float(p)) for p in value[value.index("(") + 1 : value.index(")")].split(",")]
        return QColor(r, g, b, a)
    return QColor(value)


def with_alpha(value, alpha):
    color = qcolor(value)
    color.setAlpha(alpha)
    return color
