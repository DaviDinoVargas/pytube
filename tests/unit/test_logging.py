import logging

import pytest

from app import logging_setup as ls


@pytest.fixture(autouse=True)
def clean_handlers():
    yield
    root = logging.getLogger("dinotube")
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()


@pytest.mark.parametrize("raw,must_not_contain", [
    ("GET https://rr1---sn-abc.googlevideo.com/videoplayback?expire=123&sig=SEGREDO&id=1", "SEGREDO"),
    ("url=https://x.test/a?token=ABC123&ok=1", "ABC123"),
    ("Authorization: Bearer abc.def.ghi", "abc.def.ghi"),
    ("Cookie: SID=zzz; HSID=yyy", "zzz"),
    ("set-cookie: a=b", "a=b"),
    ("password=hunter2 user=x", "hunter2"),
    ("po_token=XYZ visitor_data=Cgt", "XYZ"),
    ("api_key=KKK", "KKK"),
])
def test_secrets_are_redacted(raw, must_not_contain):
    out = ls.redact(raw)
    assert must_not_contain not in out and ls.REDACTED in out


def test_harmless_text_is_untouched():
    text = "Download concluído: Meu vídeo [720p].mp4 em 12.3s"
    assert ls.redact(text) == text


def test_log_file_is_written_and_redacted(tmp_path):
    ls.setup_logging(tmp_path / "logs")
    log = ls.get_logger("teste")
    log.info("baixando https://rr2.googlevideo.com/videoplayback?sig=SECRETO&x=1 para %s", "pasta")
    log.warning("falhou com token=ABC")
    for h in logging.getLogger("dinotube").handlers:
        h.flush()
    content = (tmp_path / "logs" / ls.LOG_NAME).read_text(encoding="utf-8")
    assert "SECRETO" not in content and "ABC" not in content and "pasta" in content and "WARNING" in content


def test_exception_traces_are_redacted(tmp_path):
    ls.setup_logging(tmp_path / "logs")
    try:
        raise ValueError("falha em https://a.googlevideo.com/v?sig=ULTRA")
    except ValueError:
        ls.get_logger("x").exception("erro")
    content = (tmp_path / "logs" / ls.LOG_NAME).read_text(encoding="utf-8")
    assert "ULTRA" not in content


def test_setup_is_idempotent_and_can_switch_folder(tmp_path):
    ls.setup_logging(tmp_path / "a")
    ls.setup_logging(tmp_path / "a")
    handlers = [h for h in logging.getLogger("dinotube").handlers if getattr(h, "_dinotube", False)]
    assert len(handlers) == 1
    ls.setup_logging(tmp_path / "b")
    ls.get_logger("x").info("depois da troca")
    assert "depois da troca" in (tmp_path / "b" / ls.LOG_NAME).read_text(encoding="utf-8")
    assert not (tmp_path / "a" / ls.LOG_NAME).read_text(encoding="utf-8").count("depois da troca")


def test_log_rotates_and_keeps_limited_files(tmp_path, monkeypatch):
    monkeypatch.setattr(ls, "MAX_BYTES", 2000)
    ls.setup_logging(tmp_path / "logs")
    log = ls.get_logger("r")
    for i in range(400):
        log.info("linha %d com algum texto para encher o arquivo", i)
    names = sorted(p.name for p in (tmp_path / "logs").iterdir())
    assert len(names) <= ls.BACKUPS + 1 and ls.LOG_NAME in names


def test_excepthook_logs_then_delegates(tmp_path, monkeypatch):
    import sys

    seen = []
    monkeypatch.setattr(sys, "excepthook", lambda *a: seen.append(a))
    ls.setup_logging(tmp_path / "logs")
    ls.install_excepthook()
    try:
        raise RuntimeError("boom token=SEGREDO")
    except RuntimeError:
        sys.excepthook(*sys.exc_info())
    assert seen and "boom" in (tmp_path / "logs" / ls.LOG_NAME).read_text(encoding="utf-8")
    assert "SEGREDO" not in (tmp_path / "logs" / ls.LOG_NAME).read_text(encoding="utf-8")
