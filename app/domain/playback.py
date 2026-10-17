"""Regras de reprodução independentes de interface: qualidades do YouTube, velocidades e retomada."""

# Nomes de qualidade da API do player incorporado do YouTube -> altura em pixels
YT_LEVELS = {
    "tiny": 144, "small": 240, "medium": 360, "large": 480,
    "hd720": 720, "hd1080": 1080, "hd1440": 1440, "hd2160": 2160, "highres": 4320,
}
_HEIGHT_TO_LEVEL = {height: level for level, height in YT_LEVELS.items()}

SPEEDS = (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)
SEEK_STEP = 5  # segundos por toque de seta
VOLUME_STEP = 5

RESUME_MIN = 5.0  # abaixo disso, recomeça do início
RESUME_END_MARGIN = 5.0  # a menos de 5 s do fim, considera terminado
WATCHED_FRACTION = 0.95


def height_from_level(level):
    """Altura correspondente a um nível do YouTube ('hd1080' -> 1080). None para 'auto' ou desconhecido."""
    return YT_LEVELS.get(level)


def level_from_height(height):
    """Nível do YouTube mais próximo de uma altura em pixels."""
    if height in _HEIGHT_TO_LEVEL:
        return _HEIGHT_TO_LEVEL[height]
    nearest = min(YT_LEVELS.values(), key=lambda h: abs(h - height))
    return _HEIGHT_TO_LEVEL[nearest]


def available_heights(levels):
    """Alturas (maior primeiro) de uma lista de níveis do YouTube; ignora 'auto' e desconhecidos."""
    heights = {YT_LEVELS[level] for level in levels or [] if level in YT_LEVELS}
    return sorted(heights, reverse=True)


def is_watched(position, duration):
    return bool(duration) and duration > 0 and position >= duration * WATCHED_FRACTION


def resume_position(progress, duration=None):
    """Segundo em que retomar o vídeo, ou 0 se deve começar do início."""
    if progress is None or progress.watched:
        return 0.0
    position = max(0.0, float(progress.position or 0))
    total = duration or progress.duration
    if position < RESUME_MIN:
        return 0.0
    if total and position > total - RESUME_END_MARGIN:
        return 0.0
    return position


def clamp_seek(position, duration):
    position = max(0.0, position)
    if duration and duration > 0:
        position = min(position, duration)
    return position
