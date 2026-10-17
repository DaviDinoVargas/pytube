import pytest

from app.domain import playback
from app.domain.models import Progress


@pytest.mark.parametrize("level,height", [("tiny", 144), ("medium", 360), ("hd720", 720), ("hd1080", 1080), ("hd2160", 2160), ("auto", None), ("???", None)])
def test_height_from_level(level, height):
    assert playback.height_from_level(level) == height


@pytest.mark.parametrize("height,level", [(720, "hd720"), (1080, "hd1080"), (700, "hd720"), (1000, "hd1080"), (10, "tiny"), (99999, "highres")])
def test_level_from_height_uses_nearest(height, level):
    assert playback.level_from_height(height) == level


def test_available_heights_ignores_auto_and_unknown_and_sorts_desc():
    assert playback.available_heights(["hd720", "auto", "tiny", "hd1080", "xyz", "hd720"]) == [1080, 720, 144]
    assert playback.available_heights(None) == [] and playback.available_heights([]) == []


@pytest.mark.parametrize("pos,dur,watched", [(95, 100, True), (94.9, 100, False), (100, 100, True), (10, None, False), (10, 0, False)])
def test_is_watched(pos, dur, watched):
    assert playback.is_watched(pos, dur) is watched


@pytest.mark.parametrize("progress,duration,expected", [
    (None, 100, 0.0),
    (Progress(1, position=42), 100, 42.0),
    (Progress(1, position=3), 100, 0.0),        # curto demais: recomeça
    (Progress(1, position=5), 100, 5.0),
    (Progress(1, position=97), 100, 0.0),       # quase no fim: recomeça
    (Progress(1, position=42, watched=True), 100, 0.0),
    (Progress(1, position=42, duration=40), None, 0.0),  # posição inválida para a mídia
    (Progress(1, position=42), None, 42.0),
])
def test_resume_position(progress, duration, expected):
    assert playback.resume_position(progress, duration) == expected


def test_clamp_seek():
    assert playback.clamp_seek(-5, 100) == 0 and playback.clamp_seek(150, 100) == 100 and playback.clamp_seek(50, None) == 50
