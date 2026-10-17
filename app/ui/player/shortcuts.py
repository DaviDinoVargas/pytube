"""Atalhos de teclado do player e a regra de quando NÃO capturá-los."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractButton, QAbstractSlider, QAbstractSpinBox, QComboBox, QLineEdit, QTextEdit

from app.domain import playback

PLAY_PAUSE = "play_pause"
SEEK_BACK = "seek_back"
SEEK_FORWARD = "seek_forward"
VOLUME_UP = "volume_up"
VOLUME_DOWN = "volume_down"
MUTE = "mute"
FULLSCREEN = "fullscreen"
EXIT_FULLSCREEN = "exit_fullscreen"

KEYMAP = {
    Qt.Key_Space: PLAY_PAUSE,
    Qt.Key_K: PLAY_PAUSE,
    Qt.Key_Left: SEEK_BACK,
    Qt.Key_Right: SEEK_FORWARD,
    Qt.Key_Up: VOLUME_UP,
    Qt.Key_Down: VOLUME_DOWN,
    Qt.Key_M: MUTE,
    Qt.Key_F: FULLSCREEN,
    Qt.Key_Escape: EXIT_FULLSCREEN,
}


def action_for(key, modifiers=Qt.NoModifier):
    """Ação do player para uma tecla. Combinações com Ctrl/Alt/Meta pertencem a outros atalhos do app."""
    if modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier):
        return None
    return KEYMAP.get(key)


def should_ignore(focus_widget, action):
    """Digitando em um campo, ou com um controle que já usa a tecla em foco, o atalho não deve disparar."""
    if isinstance(focus_widget, (QLineEdit, QTextEdit, QAbstractSpinBox)):
        return True
    if isinstance(focus_widget, QComboBox):
        return True
    if isinstance(focus_widget, QAbstractSlider) and action in (SEEK_BACK, SEEK_FORWARD, VOLUME_UP, VOLUME_DOWN):
        return True
    if isinstance(focus_widget, QAbstractButton) and action == PLAY_PAUSE:
        return True  # Espaço já aciona o botão focado
    return False


def seek_delta(action):
    return {SEEK_BACK: -playback.SEEK_STEP, SEEK_FORWARD: playback.SEEK_STEP}.get(action, 0)


def volume_delta(action):
    return {VOLUME_UP: playback.VOLUME_STEP, VOLUME_DOWN: -playback.VOLUME_STEP}.get(action, 0)
