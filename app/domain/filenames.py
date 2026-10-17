import re
from pathlib import Path

_FORBIDDEN = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
MAX_STEM = 120


def safe_filename(name, fallback="video"):
    """Nome de arquivo seguro no Windows e no Linux: sem separadores, sem reservados e com tamanho limitado."""
    text = _FORBIDDEN.sub("_", name or "")
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    text = text.lstrip(".")  # nada de arquivo oculto nem '..'
    if len(text) > MAX_STEM:
        text = text[:MAX_STEM].rstrip(" .")
    if not text or text.split(".")[0].upper() in _RESERVED:
        text = f"{fallback}_{text}" if text else fallback
    return text


def unique_path(folder, stem, suffix):
    """Caminho que não existe ainda: 'nome.mp4', 'nome (2).mp4', 'nome (3).mp4'… Nunca sobrescreve."""
    folder = Path(folder)
    candidate = folder / f"{stem}{suffix}"
    n = 2
    while candidate.exists():
        candidate = folder / f"{stem} ({n}){suffix}"
        n += 1
    return candidate
