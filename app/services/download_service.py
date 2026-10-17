import os
import shutil
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from app.domain.errors import DuplicateError, NotFoundError, StorageError
from app.domain.filenames import safe_filename, unique_path
from app.domain.states import DOWNLOADED, video_state
from app.infrastructure.media.ffmpeg import MediaError, MergeCancelled
from app.infrastructure.providers import quality
from app.infrastructure.providers.base import DownloadCancelled, ProviderError

QUEUED = "queued"
RESOLVING = "resolving"
DOWNLOADING = "downloading"
MERGING = "merging"
FINALIZING = "finalizing"
COMPLETED = "completed"
FAILED = "failed"
CANCELLED = "cancelled"

RUNNING = frozenset({RESOLVING, DOWNLOADING, MERGING, FINALIZING})
ACTIVE = RUNNING | {QUEUED}
FINISHED = frozenset({COMPLETED, FAILED, CANCELLED})

# Faixa do progresso total reservada a cada etapa
_DOWNLOAD_SHARE = 0.90
_MERGE_SHARE = 0.08
_EMIT_INTERVAL = 0.15
_SPACE_MARGIN_MERGE = 2.2  # partes + arquivo final
_SPACE_MARGIN_DIRECT = 1.15
_SPEED_WINDOW = 3.0


@dataclass
class DownloadTask:
    id: int
    video_id: int
    source_id: str
    title: str
    height: int | None = None
    replace: bool = False
    label: str = ""
    status: str = QUEUED
    progress: float = 0.0
    speed: float = 0.0  # bytes/s
    eta: float | None = None  # segundos
    bytes_done: int = 0
    bytes_total: int = 0
    error_code: str = ""
    error_detail: str = ""
    final_path: str = ""
    attempt: int = 1
    provider: str = ""

    @property
    def finished(self):
        return self.status in FINISHED


class DownloadManager(QObject):
    """Fila de downloads: limite de simultâneos, progresso, cancelamento, nova tentativa e validação do arquivo."""

    task_changed = Signal(int)  # qualquer mudança, inclusive progresso (limitado a ~7 por segundo)
    queue_changed = Signal()  # entrada ou saída de tarefas e mudança de estado

    def __init__(self, library, providers, tools_getter, max_concurrent=2, free_space=None):
        super().__init__()
        self._library = library
        self._providers = providers
        self._tools_getter = tools_getter
        self._max = max(1, int(max_concurrent))
        self._free_space = free_space or (lambda path: shutil.disk_usage(path).free)
        self._tasks = []
        self._next_id = 1
        self._lock = threading.RLock()
        self._cancel = {}
        self._threads = {}
        self._last_emit = {}
        self._closing = False

    # -- consulta ---------------------------------------------------------------
    def tasks(self):
        with self._lock:
            return list(self._tasks)

    def get(self, task_id):
        with self._lock:
            return next((t for t in self._tasks if t.id == task_id), None)

    def active_count(self):
        with self._lock:
            return sum(1 for t in self._tasks if t.status in ACTIVE)

    def task_for_video(self, video_id):
        """Tarefa mais recente do vídeo (ativa tem prioridade)."""
        with self._lock:
            mine = [t for t in self._tasks if t.video_id == video_id]
        active = [t for t in mine if t.status in ACTIVE]
        return (active or mine or [None])[-1]

    def status_for_video(self, video_id):
        """'downloading' se há tarefa ativa; 'failed' se a última falhou e não há arquivo; senão None."""
        task = self.task_for_video(video_id)
        if task is None:
            return None
        if task.status in ACTIVE:
            return "downloading"
        if task.status == FAILED:
            video = self._library.get(video_id)
            if video is None or video_state(video) != DOWNLOADED:
                return "failed"
        return None

    # -- comandos ----------------------------------------------------------------
    def set_max_concurrent(self, value):
        self._max = max(1, int(value))
        self._pump()

    def enqueue(self, video_id, height=None, replace=False):
        video = self._library.get(video_id)
        if video is None:
            raise NotFoundError(f"video {video_id}")
        with self._lock:
            if any(t.video_id == video_id and t.status in ACTIVE for t in self._tasks):
                raise DuplicateError("already_queued")
            video = self._library.validate_local(video)
            if video_state(video) == DOWNLOADED and not replace:
                raise DuplicateError("already_downloaded")
            task = DownloadTask(self._next_id, video_id, video.source_id, video.title, height, replace)
            self._next_id += 1
            self._tasks.append(task)
        self.queue_changed.emit()
        self.task_changed.emit(task.id)
        self._pump()
        return task

    def cancel(self, task_id):
        with self._lock:
            task = self.get(task_id)
            if task is None or task.finished:
                return
            if task.status == QUEUED:
                task.status = CANCELLED
            else:
                self._cancel[task_id].set()
                return
        self._notify(task, force=True, transition=True)

    def retry(self, task_id):
        """Nova tentativa de uma tarefa que falhou ou foi cancelada."""
        with self._lock:
            task = self.get(task_id)
            if task is None or task.status not in (FAILED, CANCELLED):
                return None
            if any(t.video_id == task.video_id and t.status in ACTIVE for t in self._tasks):
                raise DuplicateError("already_queued")
            task.status, task.progress, task.speed, task.eta = QUEUED, 0.0, 0.0, None
            task.bytes_done = task.bytes_total = 0
            task.error_code = task.error_detail = ""
            task.attempt += 1
        self._notify(task, force=True, transition=True)
        self._pump()
        return task

    def remove(self, task_id):
        with self._lock:
            task = self.get(task_id)
            if task is None or not task.finished:
                return
            self._tasks.remove(task)
        self.queue_changed.emit()

    def clear_finished(self, only_completed=False):
        with self._lock:
            keep = [t for t in self._tasks if not t.finished or (only_completed and t.status != COMPLETED)]
            changed = len(keep) != len(self._tasks)
            self._tasks = keep
        if changed:
            self.queue_changed.emit()

    def cleanup_orphans(self):
        """Apaga restos de downloads interrompidos (de uma execução anterior) da pasta tmp/."""
        if not self._library.ready:
            return
        with self._lock:
            running = {t.id for t in self._tasks if t.status in RUNNING}
        tmp = self._library.layout.tmp
        if not tmp.is_dir():
            return
        for entry in tmp.iterdir():
            task_id = entry.name.split("-", 1)[0]
            if task_id.isdigit() and int(task_id) in running:
                continue
            shutil.rmtree(entry, ignore_errors=True) if entry.is_dir() else entry.unlink(missing_ok=True)

    def shutdown(self, timeout=8.0):
        """Cancela o que está em andamento e espera as threads terminarem."""
        self._closing = True
        with self._lock:
            events = list(self._cancel.values())
            threads = list(self._threads.values())
            for task in self._tasks:
                if task.status == QUEUED:
                    task.status = CANCELLED
        for event in events:
            event.set()
        deadline = time.monotonic() + timeout
        for thread in threads:
            thread.join(max(0.0, deadline - time.monotonic()))

    # -- agendamento -----------------------------------------------------------------
    def _pump(self):
        with self._lock:
            if self._closing:
                return
            running = sum(1 for t in self._tasks if t.status in RUNNING)
            for task in self._tasks:
                if running >= self._max:
                    break
                if task.status != QUEUED:
                    continue
                task.status = RESOLVING  # reservado antes de iniciar a thread
                event = threading.Event()
                self._cancel[task.id] = event
                thread = threading.Thread(target=self._worker, args=(task, event), daemon=True, name=f"download-{task.id}")
                self._threads[task.id] = thread
                running += 1
                thread.start()

    def _notify(self, task, force=False, transition=False):
        now = time.monotonic()
        if force or now - self._last_emit.get(task.id, 0) >= _EMIT_INTERVAL:
            self._last_emit[task.id] = now
            self.task_changed.emit(task.id)
        if transition:
            self.queue_changed.emit()

    def _set_status(self, task, status):
        task.status = status
        self._notify(task, force=True, transition=True)

    # -- execução ----------------------------------------------------------------------
    def _worker(self, task, cancel):
        outcome = (COMPLETED, "", "")
        try:
            self._notify(task, force=True, transition=True)
            self._execute(task, cancel)
        except (DownloadCancelled, MergeCancelled):
            outcome = (CANCELLED, "", "")
        except ProviderError as exc:
            outcome = (FAILED, exc.code, exc.detail)
        except (MediaError, StorageError) as exc:
            outcome = (FAILED, exc.code, exc.detail)
        except OSError as exc:
            outcome = (FAILED, "io_error", str(exc)[:300])
        except Exception as exc:  # uma falha inesperada nunca derruba o aplicativo
            outcome = (FAILED, "failed", repr(exc)[:300])
        # O estado final só é publicado depois da limpeza: quem vê "concluído" já encontra tmp/ vazia.
        tmp = self._tmp_dir(task)
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
        self._finish(task, *outcome)
        with self._lock:
            self._cancel.pop(task.id, None)
            self._threads.pop(task.id, None)
        self._pump()

    def _finish(self, task, status, code="", detail=""):
        task.error_code, task.error_detail = code, detail
        task.speed, task.eta = 0.0, None
        if status == COMPLETED:
            task.progress = 1.0
        self._set_status(task, status)

    def _tmp_dir(self, task):
        if not self._library.ready:
            return None
        return self._library.layout.tmp / f"{task.id}-{task.source_id}"

    @staticmethod
    def _check(cancel):
        if cancel.is_set():
            raise DownloadCancelled()

    def _execute(self, task, cancel):
        layout = self._library.layout
        tools = self._tools_getter()  # levanta MediaError se o ffmpeg faltar ou for antigo
        info = self._providers.fetch_info(task.source_id)
        self._check(cancel)
        task.provider = info.provider
        height = task.height or quality.default_height(info.streams)
        if height is None:
            raise ProviderError("unsupported", "nenhuma qualidade disponível")
        selection = quality.pick(info.streams, height)
        task.height, task.label = height, selection.label

        parts = [selection.video] + ([selection.audio] if selection.audio else [])
        estimated = sum(p.filesize or 0 for p in parts)
        if estimated:
            needed = estimated * (_SPACE_MARGIN_MERGE if selection.audio else _SPACE_MARGIN_DIRECT)
            if self._free_space(layout.root) < needed:
                raise StorageError("no_space", f"{int(needed)} bytes")
        task.bytes_total = estimated

        tmp_dir = self._tmp_dir(task)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        self._set_status(task, DOWNLOADING)
        paths = self._download_parts(task, info, parts, tmp_dir, cancel)
        self._check(cancel)

        if selection.audio is not None:
            self._set_status(task, MERGING)
            out = tmp_dir / "out.mp4"
            copy_video, copy_audio = quality.recode_plan(selection)
            base = _DOWNLOAD_SHARE

            def merge_progress(fraction):
                task.progress = base + _MERGE_SHARE * fraction
                self._notify(task)

            tools.merge(paths[0], paths[1], out, copy_video, copy_audio, duration=info.duration,
                        on_progress=merge_progress, cancel_event=cancel)
            suffix = ".mp4"
        else:
            suffix = "." + (selection.video.ext or "mp4")
            out = paths[0]
        self._check(cancel)

        self._set_status(task, FINALIZING)
        self._validate(tools, out, info, expect_audio=True)
        final = self._move_to_library(task, out, suffix)
        old = self._library.local_path(self._library.get(task.video_id), must_exist=False)
        self._library.attach_local_file(task.video_id, final, task.label)
        if task.replace and old is not None and old != final.resolve() and old.is_file():
            self._delete_inside_library(old)
        task.final_path = str(final)

    def _download_parts(self, task, info, parts, tmp_dir, cancel):
        paths = []
        finished_bytes = 0
        samples = deque()
        totals = [p.filesize or 0 for p in parts]
        for index, part in enumerate(parts):
            dest = tmp_dir / f"{'video' if part.kind != 'audio' else 'audio'}.{part.ext or 'mp4'}"

            def on_progress(done, total, index=index):
                if cancel.is_set():
                    raise DownloadCancelled()
                if total:
                    totals[index] = total
                overall_total = sum(totals) or 1
                overall_done = finished_bytes + done
                task.bytes_done, task.bytes_total = overall_done, overall_total
                task.progress = max(task.progress, min(_DOWNLOAD_SHARE, overall_done / overall_total * _DOWNLOAD_SHARE))
                now = time.monotonic()
                samples.append((now, overall_done))
                while samples and now - samples[0][0] > _SPEED_WINDOW:
                    samples.popleft()
                if len(samples) > 1 and now > samples[0][0]:
                    task.speed = max(0.0, (overall_done - samples[0][1]) / (now - samples[0][0]))
                    remaining = overall_total - overall_done
                    task.eta = remaining / task.speed if task.speed > 0 else None
                self._notify(task)

            self._providers.download(info, part, dest, on_progress, cancel)
            if not dest.is_file() or dest.stat().st_size == 0:
                raise ProviderError("failed", f"parte vazia: {dest.name}")
            finished_bytes += dest.stat().st_size
            totals[index] = dest.stat().st_size
            paths.append(dest)
        return paths

    @staticmethod
    def _validate(tools, path, info, expect_audio):
        """O arquivo só vale como baixado se o ffprobe confirmar vídeo, áudio e duração coerente."""
        media = tools.probe(path)
        if not media.has_video or (expect_audio and not media.has_audio) or media.duration <= 0:
            raise MediaError("invalid_media", "sem vídeo, sem áudio ou sem duração")
        if info.duration and abs(media.duration - info.duration) > max(5.0, 0.05 * info.duration):
            raise MediaError("invalid_media", f"duração {media.duration:.0f}s difere de {info.duration}s")

    def _move_to_library(self, task, source, suffix):
        layout = self._library.layout
        layout.videos.mkdir(parents=True, exist_ok=True)
        stem = f"{safe_filename(task.title, task.source_id)} [{task.label}]"
        final = unique_path(layout.videos, stem, suffix)  # nunca sobrescreve um arquivo existente
        try:
            os.replace(source, final)
        except OSError:
            shutil.move(str(source), str(final))
        return final

    def _delete_inside_library(self, path):
        videos = self._library.layout.videos.resolve()
        try:
            if Path(path).resolve().is_relative_to(videos):
                Path(path).unlink()
        except OSError:
            pass
