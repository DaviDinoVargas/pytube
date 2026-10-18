from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget


class PlayerBackend(QWidget):
    """Contrato comum aos motores de reprodução (arquivo local, player do YouTube, stream direto)."""

    loaded = Signal()  # mídia pronta
    state_changed = Signal(bool)  # tocando?
    position_changed = Signal(float, float)  # posição e duração, em segundos
    quality_changed = Signal(int, list)  # altura em reprodução (0 = desconhecida) e alturas disponíveis
    status_changed = Signal(int, bool, float)  # volume 0-100, mudo, velocidade
    error = Signal(str, str)  # código estável, detalhe
    ended = Signal()
    clicked = Signal()  # clique sobre a imagem do vídeo

    def play(self):
        raise NotImplementedError

    def pause(self):
        raise NotImplementedError

    def toggle(self):
        """Alterna tocar/pausar usando o estado real do motor, não o último que ele nos avisou."""
        self.pause() if self.is_playing() else self.play()

    def stop(self):
        raise NotImplementedError

    def seek(self, seconds):
        raise NotImplementedError

    def set_volume(self, percent):
        raise NotImplementedError

    def set_muted(self, muted):
        raise NotImplementedError

    def set_rate(self, rate):
        raise NotImplementedError

    def set_quality(self, height):
        """Pede uma qualidade. Motores que não trocam de qualidade ignoram."""

    def can_change_quality(self):
        return False

    def position(self):
        return 0.0

    def duration(self):
        return 0.0

    def is_playing(self):
        return False
