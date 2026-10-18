from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

_active = set()  # mantém as tarefas vivas até terminarem


class _Job(QObject):
    """Vive na thread da interface: `_deliver` roda sempre lá, mesmo com o trabalho feito em outra thread."""

    finished = Signal(object, object)

    def __init__(self, on_done, on_error):
        super().__init__()
        self._on_done = on_done
        self._on_error = on_error
        self.finished.connect(self._deliver)

    @Slot(object, object)
    def _deliver(self, result, error):
        _active.discard(self)
        try:
            if error is not None:
                if self._on_error:
                    self._on_error(error)
            elif self._on_done:
                self._on_done(result)
        except RuntimeError as exc:
            if "already deleted" not in str(exc):  # a janela fechou antes de a tarefa terminar: não há mais onde mostrar
                raise
        finally:
            self.deleteLater()


class _Runner(QRunnable):
    def __init__(self, job, fn):
        super().__init__()
        self._job = job
        self._fn = fn

    def run(self):
        try:
            result, error = self._fn(), None
        except Exception as exc:  # a falha de uma tarefa nunca derruba o app
            result, error = None, exc
        self._job.finished.emit(result, error)


def run_async(fn, on_done=None, on_error=None):
    """Executa `fn` em uma thread do pool e entrega o resultado (ou o erro) na thread da interface."""
    job = _Job(on_done, on_error)
    _active.add(job)
    QThreadPool.globalInstance().start(_Runner(job, fn))
    return job
