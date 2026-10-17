"""Logs rotativos que nunca gravam tokens, cookies, assinaturas ou URLs temporárias de vídeo."""

import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_NAME = "dinotube.log"
MAX_BYTES = 512 * 1024
BACKUPS = 3
REDACTED = "<redigido>"

_PATTERNS = (
    # URLs de stream do YouTube carregam credenciais temporárias na query: corta tudo depois do '?'
    (re.compile(r"(https?://[^\s\"']*googlevideo\.com/[^\s\"'?]*)\?[^\s\"']*", re.I), r"\1?" + REDACTED),
    (re.compile(r"(?i)\b(authorization|cookie|set-cookie|proxy-authorization)\b\s*[:=]\s*[^\r\n]+"), r"\1: " + REDACTED),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer " + REDACTED),
    (re.compile(
        r"(?i)\b(signature|sig|sign|token|access_token|api_?key|key|password|passwd|secret|session|expire|po_token|visitor_data|n)=([^&\s\"']+)"),
        r"\1=" + REDACTED),
)


def redact(text):
    """Remove de `text` o que pode vazar acesso: tokens, cookies, senhas e credenciais de URL."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record):
        record.msg = redact(record.getMessage())
        record.args = ()
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True


def _file_handler(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(directory / LOG_NAME, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(RedactingFilter())
    handler._dinotube = True
    return handler


def setup_logging(directory, level=logging.INFO):
    """Liga o log em arquivo em `directory`. Chamar de novo troca a pasta (ex.: ao trocar a biblioteca)."""
    root = logging.getLogger("dinotube")
    root.setLevel(level)
    root.propagate = False
    for handler in list(root.handlers):
        if getattr(handler, "_dinotube", False):
            root.removeHandler(handler)
            handler.close()
    root.addHandler(_file_handler(directory))
    return root


def get_logger(name):
    return logging.getLogger(f"dinotube.{name}")


def install_excepthook():
    """Erros não tratados vão para o log (sem dados sensíveis) e depois seguem o tratamento padrão do Python."""
    previous = sys.excepthook

    def hook(exc_type, exc, tb):
        logging.getLogger("dinotube").error("Erro não tratado", exc_info=(exc_type, exc, tb))
        previous(exc_type, exc, tb)

    sys.excepthook = hook
