"""Marcadores de tempo dentro das notas: '[12:34] trecho importante' vira um item clicável que leva o player até lá."""

import re
from dataclasses import dataclass

_MARK = re.compile(r"\[(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\]")
LABEL_LIMIT = 80


@dataclass(frozen=True)
class Marker:
    seconds: int
    label: str  # texto da linha, sem o marcador


def parse_markers(text):
    """Todos os marcadores [m:ss] ou [h:mm:ss] do texto, em ordem de aparição. Minutos/segundos fora de 0-59 são ignorados."""
    out = []
    for line in (text or "").splitlines():
        for match in _MARK.finditer(line):
            hours, minutes, seconds = (int(x) if x is not None else 0 for x in match.groups())
            if minutes > 59 or seconds > 59:
                continue
            label = (line[:match.start()] + line[match.end():]).strip(" \t-–—:")
            out.append(Marker(hours * 3600 + minutes * 60 + seconds, label[:LABEL_LIMIT]))
    return out
