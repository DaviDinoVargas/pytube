from PySide6.QtCore import QEvent, QObject, QTimer, Signal
from PySide6.QtGui import QCursor, QGuiApplication


class IdleWatcher(QObject):
    """Avisa quando o usuário para de mexer o mouse e o teclado (e quando volta). O mouse é verificado por polling da posição do
    cursor, porque o widget de vídeo nativo não entrega eventos de movimento ao Qt."""

    active_changed = Signal(bool)  # True: voltou a mexer; False: ficou ocioso

    def __init__(self, parent=None, timeout_ms=2500, interval_ms=150):
        super().__init__(parent)
        self._timeout = timeout_ms
        self._active = True
        self._last_pos = None
        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.setInterval(timeout_ms)
        self._idle.timeout.connect(self._go_idle)
        self._poll = QTimer(self)
        self._poll.setInterval(interval_ms)
        self._poll.timeout.connect(self._tick)
        self._running = False

    @property
    def active(self):
        return self._active

    @property
    def running(self):
        return self._running

    def start(self):
        if self._running:
            return
        self._running = True
        self._last_pos = QCursor.pos()
        QGuiApplication.instance().installEventFilter(self)
        self._poll.start()
        self.poke()

    def stop(self):
        if not self._running:
            return
        self._running = False
        self._poll.stop()
        self._idle.stop()
        QGuiApplication.instance().removeEventFilter(self)
        self._set_active(True)

    def poke(self):
        """Registra atividade: mostra de novo e reinicia a contagem."""
        if not self._running:
            return
        self._set_active(True)
        self._idle.start()

    def eventFilter(self, _obj, event):
        if event.type() in (QEvent.KeyPress, QEvent.MouseButtonPress, QEvent.Wheel):
            self.poke()
        return False

    def _tick(self):
        pos = QCursor.pos()
        if pos != self._last_pos or QGuiApplication.mouseButtons():
            self._last_pos = pos
            self.poke()

    def _go_idle(self):
        self._set_active(False)

    def _set_active(self, active):
        if active != self._active:
            self._active = active
            self.active_changed.emit(active)
