import subprocess
import sys
from dataclasses import dataclass
from importlib import metadata

from app.logging_setup import redact

PACKAGES = {"pytubefix": "pytubefix", "ytdlp": "yt-dlp"}  # nome do provedor -> pacote do pip
MAX_OUTPUT = 4000


@dataclass(frozen=True)
class UpdateResult:
    ok: bool
    code: str  # '' | 'frozen' | 'failed' | 'timeout' | 'no_pip'
    output: str = ""


def installed_versions():
    """Versão instalada de cada provedor, ou None se o pacote não estiver instalado."""
    versions = {}
    for name, package in PACKAGES.items():
        try:
            versions[name] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def can_self_update(frozen=None):
    """A atualização usa o pip do Python. No executável empacotado não existe pip: a saída é baixar uma versão nova."""
    return not (getattr(sys, "frozen", False) if frozen is None else frozen)


def update_providers(runner=subprocess.run, frozen=None, timeout=300):
    """Atualiza pytubefix e yt-dlp. O YouTube muda e eles quebram; atualizar costuma consertar. Precisa reiniciar depois."""
    if not can_self_update(frozen):
        return UpdateResult(False, "frozen")
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "--disable-pip-version-check", *PACKAGES.values()]
    try:
        result = runner(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return UpdateResult(False, "timeout")
    except OSError as exc:
        return UpdateResult(False, "no_pip", redact(str(exc))[:MAX_OUTPUT])
    output = redact((result.stdout or "") + (result.stderr or ""))[-MAX_OUTPUT:]
    if result.returncode != 0:
        return UpdateResult(False, "failed", output)
    return UpdateResult(True, "", output)
