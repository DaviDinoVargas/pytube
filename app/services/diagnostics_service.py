import platform
import sys
from pathlib import Path

from app import APP_NAME, APP_VERSION
from app.logging_setup import LOG_NAME, redact
from app.services.provider_service import installed_versions

LOG_LINES = 40


def scrub_paths(text, home=None):
    """Troca a pasta pessoal (e portanto o nome de usuário) por '~' para o relatório poder ser compartilhado."""
    home = str(home or Path.home())
    if home and home not in ("/", "\\"):
        text = text.replace(home, "~").replace(home.replace("\\", "/"), "~")
    return text


def build_report(settings, storage, library, tools=None, providers=None, home=None):
    """Texto de diagnóstico: versões, configuração e contagens. Sem URLs de vídeo, tokens, cookies ou seu nome de usuário."""
    lines = [f"{APP_NAME} {APP_VERSION}", f"Python {sys.version.split()[0]} · {platform.system()} {platform.release()}"]
    try:
        import PySide6
        from PySide6.QtCore import qVersion

        lines.append(f"PySide6 {PySide6.__version__} · Qt {qVersion()}")
    except Exception:
        lines.append("PySide6 indisponível")
    lines.append("")
    lines.append("Provedores")
    versions = installed_versions()
    available = {p.name: p.is_available() for p in (providers.available() if providers else [])}
    for name, version in versions.items():
        lines.append(f"  {name}: {version or 'não instalado'}" + (" (ativo)" if name in available else ""))
    if providers is not None:
        lines.append(f"  ordem: {' > '.join(providers.order)}")
    lines.append("")
    lines.append("ffmpeg: " + ((getattr(tools, "version_text", "") or "versão desconhecida") if tools else "não encontrado"))
    lines.append("")
    lines.append("Biblioteca")
    if storage.status() == "ready":
        cfg = storage.config
        counts = library.store.counts()
        usage = storage.usage()
        lines.append(f"  modo: {cfg.mode} · formato: {cfg.format if cfg.mode == 'folder' else 'sqlite'}")
        lines.append(f"  vídeos: {counts['videos']} · categorias: {counts['categories']} · playlists: {counts['playlists']}")
        lines.append(f"  arquivos: {usage['video_files']} ({usage['videos_bytes'] // (1024 * 1024)} MB) · livre: {usage['free'] // (1024 ** 3)} GB")
    else:
        lines.append(f"  armazenamento: {storage.status()}")
    lines.append("")
    lines.append("Preferências")
    lines.append(f"  idioma: {settings.language} · tema: {settings.theme} · downloads simultâneos: {settings.download_concurrent}")
    if storage.status() == "ready":
        log = storage.layout.logs / LOG_NAME
        if log.is_file():
            tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-LOG_LINES:]
            lines.append("")
            lines.append(f"Últimas linhas do log ({len(tail)})")
            lines.extend("  " + line for line in tail)
    return scrub_paths(redact("\n".join(lines)), home)
