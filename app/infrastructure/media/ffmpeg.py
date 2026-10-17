"""Localiza e usa o ffmpeg/ffprobe: versão, análise do arquivo e junção de vídeo e áudio."""

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

MIN_MAJOR = 4  # usamos só opções antigas e estáveis (-c copy, libx264, aac, -movflags)
MIN_DATE_YEAR = 2021  # builds por data (gyan.dev git) anteriores a isso são considerados antigos
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0


class MediaError(Exception):
    """Falha do ffmpeg/ffprobe. `code`: ffmpeg_missing, ffmpeg_old, merge_failed, invalid_media."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


class MergeCancelled(Exception):
    pass


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    has_video: bool
    has_audio: bool
    vcodec: str = ""
    acodec: str = ""
    width: int = 0
    height: int = 0


def parse_version(text):
    """Extrai a versão de `ffmpeg -version`. Devolve ('release', (major, minor)) ou ('date', ano) ou None."""
    match = re.search(r"ffmpeg version\s+n?(\d+)\.(\d+)", text)
    if match:
        return ("release", (int(match.group(1)), int(match.group(2))))
    match = re.search(r"ffmpeg version\s+(\d{4})-\d{2}-\d{2}", text)
    if match:
        return ("date", int(match.group(1)))
    return None


def version_is_supported(parsed):
    if parsed is None:
        return True  # build com nome de versão desconhecido (ex.: de distribuição): tenta usar
    kind, value = parsed
    return value[0] >= MIN_MAJOR if kind == "release" else value >= MIN_DATE_YEAR


def _run(cmd, **kwargs):
    return subprocess.run(cmd, capture_output=True, text=True, creationflags=_NO_WINDOW, **kwargs)


class FFmpegTools:
    def __init__(self, ffmpeg, ffprobe):
        self.ffmpeg = str(ffmpeg)
        self.ffprobe = str(ffprobe)
        self.version_text = ""
        self.parsed_version = None

    def check(self):
        """Roda `ffmpeg -version`. Levanta MediaError se não executa ou se é antigo demais."""
        try:
            result = _run([self.ffmpeg, "-hide_banner", "-version"], timeout=20)
        except (OSError, subprocess.SubprocessError) as exc:
            raise MediaError("ffmpeg_missing", str(exc)) from exc
        if result.returncode != 0:
            raise MediaError("ffmpeg_missing", result.stderr[:200])
        self.version_text = result.stdout.splitlines()[0] if result.stdout else ""
        self.parsed_version = parse_version(self.version_text)
        if not version_is_supported(self.parsed_version):
            raise MediaError("ffmpeg_old", self.version_text)
        return self

    # -- análise ------------------------------------------------------------------
    def probe(self, path):
        try:
            result = _run(
                [self.ffprobe, "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise MediaError("ffmpeg_missing", str(exc)) from exc
        if result.returncode != 0:
            raise MediaError("invalid_media", result.stderr[:300])
        try:
            data = json.loads(result.stdout)
        except ValueError as exc:
            raise MediaError("invalid_media", "saída do ffprobe ilegível") from exc
        streams = data.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video" and s.get("disposition", {}).get("attached_pic") != 1), None)
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        try:
            duration = float(data.get("format", {}).get("duration") or (video or audio or {}).get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0.0
        return MediaInfo(
            duration=duration,
            has_video=video is not None,
            has_audio=audio is not None,
            vcodec=(video or {}).get("codec_name", ""),
            acodec=(audio or {}).get("codec_name", ""),
            width=int((video or {}).get("width") or 0),
            height=int((video or {}).get("height") or 0),
        )

    # -- junção -------------------------------------------------------------------------
    @staticmethod
    def merge_command(ffmpeg, video, audio, output, copy_video=True, copy_audio=True):
        """Comando de junção. Copia os fluxos que já são compatíveis com MP4 e só recodifica o que precisa."""
        cmd = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-progress", "pipe:1", "-nostats",
               "-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0"]
        if copy_video:
            cmd += ["-c:v", "copy"]
        else:
            cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
        if copy_audio:
            cmd += ["-c:a", "copy"]
        else:
            cmd += ["-c:a", "aac", "-b:a", "192k"]
        cmd += ["-movflags", "+faststart", "-f", "mp4", str(output)]
        return cmd

    def merge(self, video, audio, output, copy_video=True, copy_audio=True, duration=None, on_progress=None, cancel_event=None):
        """Junta vídeo e áudio em `output`. Levanta MergeCancelled se `cancel_event` for acionado."""
        cmd = self.merge_command(self.ffmpeg, video, audio, output, copy_video, copy_audio)
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=_NO_WINDOW
            )
        except OSError as exc:
            raise MediaError("ffmpeg_missing", str(exc)) from exc
        errors = []
        threading.Thread(target=lambda: errors.append(proc.stderr.read()), daemon=True).start()

        def watch():
            while proc.poll() is None:
                if cancel_event is not None and cancel_event.is_set():
                    proc.kill()
                    return
                time.sleep(0.1)

        threading.Thread(target=watch, daemon=True).start()
        for line in proc.stdout:
            if on_progress and duration and line.startswith("out_time_us="):
                try:
                    on_progress(min(1.0, int(line.split("=")[1]) / 1_000_000 / duration))
                except ValueError:
                    pass
        proc.wait()
        if cancel_event is not None and cancel_event.is_set():
            Path(output).unlink(missing_ok=True)
            raise MergeCancelled()
        if proc.returncode != 0:
            Path(output).unlink(missing_ok=True)
            time.sleep(0.05)
            raise MediaError("merge_failed", (errors[0] if errors else "")[:400])


def locate(bundled_root, override=None):
    """Acha ffmpeg e ffprobe: caminho configurado, depois o empacotado, depois o do sistema."""
    exe = ".exe" if sys.platform == "win32" else ""
    candidates = []
    if override:
        folder = Path(override)
        folder = folder if folder.is_dir() else folder.parent
        candidates.append((folder / f"ffmpeg{exe}", folder / f"ffprobe{exe}"))
    bundled = Path(bundled_root) / "third_party" / "ffmpeg" / "bin"
    candidates.append((bundled / f"ffmpeg{exe}", bundled / f"ffprobe{exe}"))
    for ffmpeg, ffprobe in candidates:
        if ffmpeg.is_file() and ffprobe.is_file():
            return FFmpegTools(ffmpeg, ffprobe)
    system_ffmpeg, system_ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if system_ffmpeg and system_ffprobe:
        return FFmpegTools(system_ffmpeg, system_ffprobe)
    return None


def bundled_root():
    """Raiz dos arquivos do app: a pasta temporária do PyInstaller ou a raiz do repositório."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)))
    return Path(__file__).resolve().parents[3]
