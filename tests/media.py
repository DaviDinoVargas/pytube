"""Gera mídia real e pequena com o ffmpeg do sistema para os testes de junção e validação."""
import shutil
import subprocess
from pathlib import Path

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
HAS_FFMPEG = bool(FFMPEG and FFPROBE)


def _run(*args):
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def make_media(folder, seconds=2):
    """Devolve {nome: Path} com: progressive_mp4, video_h264, audio_aac, video_vp9, audio_opus, garbage."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    video = f"color=c=blue:s=320x180:r=15:d={seconds}"
    audio = f"sine=frequency=440:duration={seconds}"
    out = {
        "video_h264": folder / "video_h264.mp4",
        "audio_aac": folder / "audio_aac.m4a",
        "video_vp9": folder / "video_vp9.webm",
        "audio_opus": folder / "audio_opus.webm",
        "progressive_mp4": folder / "progressive.mp4",
        "garbage": folder / "garbage.mp4",
    }
    _run("-f", "lavfi", "-i", video, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out["video_h264"]))
    _run("-f", "lavfi", "-i", audio, "-c:a", "aac", str(out["audio_aac"]))
    _run("-f", "lavfi", "-i", video, "-c:v", "libvpx-vp9", "-b:v", "200k", "-deadline", "realtime", "-cpu-used", "8", str(out["video_vp9"]))
    _run("-f", "lavfi", "-i", audio, "-c:a", "libopus", str(out["audio_opus"]))
    _run("-f", "lavfi", "-i", video, "-f", "lavfi", "-i", audio, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out["progressive_mp4"]))
    out["garbage"].write_bytes(b"isto nao e um video" * 200)
    return out
