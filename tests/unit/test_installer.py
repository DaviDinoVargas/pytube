import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packaging"))

import installer_core as core  # noqa: E402


def fake_project(tmp_path):
    root = tmp_path / "proj"
    (root / "app").mkdir(parents=True)
    (root / "app" / "__init__.py").write_text('APP_VERSION = "2.3.4"\n')
    (root / "packaging").mkdir()
    (root / "third_party" / "ffmpeg" / "bin").mkdir(parents=True)
    for name in ("DinoTube.spec", "main.py", "requirements.txt"):
        (root / name).write_text("")
    (root / "third_party" / "ffmpeg" / "bin" / "ffmpeg.exe").write_text("x")
    (root / "third_party" / "ffmpeg" / "bin" / "ffprobe.exe").write_text("x")
    return root


def fake_dist(root):
    dist = root / "dist" / "DinoTube"
    (dist / "_internal").mkdir(parents=True)
    (dist / core.EXE_NAME).write_text("exe")
    (dist / "_internal" / "lib.dll").write_text("dll" * 100)
    return dist


# -- pasta de instalação ---------------------------------------------------------------------------------------
def test_default_install_dir_is_a_per_user_programs_folder():
    path = core.default_install_dir()
    assert path.endswith("DinoTube") and Path(path).is_absolute()


def test_validate_rejects_empty_relative_root_and_project_folders(tmp_path):
    root = fake_project(tmp_path)
    assert core.validate_install_dir("", root)[0] is False
    assert core.validate_install_dir("DinoTube", root)[0] is False
    assert "projeto" in core.validate_install_dir(str(root / "dist"), root)[1]
    assert core.validate_install_dir(str(tmp_path), root)[0] is False  # pasta que contém o projeto
    assert core.validate_install_dir(str(Path(tmp_path.anchor)), root)[0] is False


def test_validate_accepts_new_folder_and_previous_install_but_not_foreign_content(tmp_path):
    root = fake_project(tmp_path)
    assert core.validate_install_dir(str(tmp_path / "apps" / "DinoTube"), root) == (True, "")
    old = tmp_path / "old"
    old.mkdir()
    (old / core.EXE_NAME).write_text("x")
    assert core.validate_install_dir(str(old), root)[0] is True  # reinstalar por cima
    foreign = tmp_path / "docs"
    foreign.mkdir()
    (foreign / "tese.docx").write_text("x")
    ok, message = core.validate_install_dir(str(foreign), root)
    assert ok is False and "outros arquivos" in message
    file = tmp_path / "arquivo"
    file.write_text("x")
    assert core.validate_install_dir(str(file), root)[0] is False


def test_validate_checks_free_space(tmp_path, monkeypatch):
    root = fake_project(tmp_path)
    monkeypatch.setattr(core, "_free_mb", lambda path: 10)
    ok, message = core.validate_install_dir(str(tmp_path / "x"), root)
    assert ok is False and "espaço" in message


def test_version_is_read_from_the_app(tmp_path, monkeypatch):
    root = fake_project(tmp_path)
    monkeypatch.setattr(core, "ROOT", root)
    assert core.app_version() == "2.3.4"


# -- scripts gerados ------------------------------------------------------------------------------------------------
def test_shortcut_script_quotes_paths_with_apostrophes():
    script = core.shortcut_script(r"C:\Users\O'Brien\DinoTube\DinoTube.exe", [r"C:\Users\O'Brien\Desktop\DinoTube.lnk"])
    assert "O''Brien" in script and script.count("CreateShortcut") == 1 and "$s.Save()" in script


def test_uninstall_batch_is_ascii_with_crlf_and_cleans_everything():
    text = core.uninstall_batch(r"C:\Apps\DinoTube", [r"C:\U\Desktop\DinoTube.lnk"])
    text.encode("ascii")  # o cmd lê na página de código do sistema: sem acentos
    assert text.count("\r\n") == text.count("\n")
    assert "taskkill" in text and "reg delete" in text and "rmdir /s /q" in text and "DinoTube.lnk" in text
    assert "MessageBox" in text  # pede confirmação antes de remover


# -- execução -----------------------------------------------------------------------------------------------------
def make_installer(tmp_path, events, **kw):
    root = fake_project(tmp_path)
    return core.Installer(tmp_path / "apps" / "DinoTube", on_event=lambda *e: events.append(e), root=root, **kw)


def test_install_step_copies_the_build_and_reports_progress(tmp_path, monkeypatch):
    events = []
    inst = make_installer(tmp_path, events)
    fake_dist(inst.root)
    inst._current = "install"
    inst._step_install()
    assert (inst.install_dir / core.EXE_NAME).read_text() == "exe"
    assert (inst.install_dir / "_internal" / "lib.dll").is_file()
    progress = [e[1] for e in events if e[0] == "progress"]
    assert progress and progress[-1] == pytest.approx((core.STEPS[0].weight * 0 + core.STEPS[-2].weight) / core.TOTAL_WEIGHT)


def test_install_replaces_a_previous_installation(tmp_path):
    inst = make_installer(tmp_path, [])
    fake_dist(inst.root)
    inst.install_dir.mkdir(parents=True)
    (inst.install_dir / core.EXE_NAME).write_text("velho")
    (inst.install_dir / "sobra.txt").write_text("x")
    inst._current = "install"
    inst._step_install()
    assert (inst.install_dir / core.EXE_NAME).read_text() == "exe" and not (inst.install_dir / "sobra.txt").exists()


def test_extras_write_the_uninstaller_outside_windows(tmp_path, monkeypatch):
    inst = make_installer(tmp_path, [])
    inst.install_dir.mkdir(parents=True)
    monkeypatch.setattr(core, "IS_WINDOWS", False)
    monkeypatch.setattr(core.Installer, "_known_folder", staticmethod(lambda name: str(tmp_path / name)))
    inst._step_extras()
    batch = (inst.install_dir / "Desinstalar.bat").read_bytes().decode("ascii")
    assert "taskkill" in batch and str(tmp_path / "Desktop" / "DinoTube.lnk") in batch
    assert len(inst.links) == 2


def test_run_executes_every_step_in_order_and_returns_the_exe(tmp_path, monkeypatch):
    events = []
    inst = make_installer(tmp_path, events)
    ran = []
    for step in core.STEPS:
        monkeypatch.setattr(inst, f"_step_{step.key}", lambda key=step.key: ran.append(key))
    assert inst.run() == ("ok", str(inst.install_dir / core.EXE_NAME))
    assert ran == [s.key for s in core.STEPS]
    states = [(e[1], e[2]) for e in events if e[0] == "step"]
    assert states[0] == ("python", core.RUNNING) and states[1] == ("python", core.DONE)
    assert [e[1] for e in events if e[0] == "progress"][-1] == 1.0


def test_run_reports_a_friendly_error_and_stops(tmp_path, monkeypatch):
    events = []
    inst = make_installer(tmp_path, events)
    ran = []

    def boom():
        raise core.InstallError("sem ffmpeg")

    for step in core.STEPS:
        monkeypatch.setattr(inst, f"_step_{step.key}", boom if step.key == "files" else (lambda key=step.key: ran.append(key)))
    assert inst.run() == ("error", "sem ffmpeg")
    assert ran == ["python"]
    assert ("step", "files", core.FAILED) in events
    assert "sem ffmpeg" in inst.log_path.read_text(encoding="utf-8")


def test_unexpected_exceptions_do_not_escape(tmp_path, monkeypatch):
    inst = make_installer(tmp_path, [])
    for step in core.STEPS:
        monkeypatch.setattr(inst, f"_step_{step.key}", lambda: 1 / 0)
    status, message = inst.run()
    assert status == "error" and "Erro inesperado" in message


def test_cancel_stops_before_the_next_step(tmp_path, monkeypatch):
    inst = make_installer(tmp_path, [])
    ran = []

    def first():
        ran.append("python")
        inst.cancel()

    monkeypatch.setattr(inst, "_step_python", first)
    for step in core.STEPS[1:]:
        monkeypatch.setattr(inst, f"_step_{step.key}", lambda key=step.key: ran.append(key))
    assert inst.run() == ("cancelled", None) and ran == ["python"]


def test_run_command_streams_output_and_maps_progress(tmp_path):
    events = []
    inst = make_installer(tmp_path, events)
    inst._current = "build"
    seen = []
    inst._run([sys.executable, "-c", "print('a'); print('Building PYZ'); print('b')"],
              progress=lambda line, n: seen.append((line, n)) or (0.5 if "PYZ" in line else None))
    logs = [e[1] for e in events if e[0] == "log"]
    assert "a" in logs and "Building PYZ" in logs and seen[-1][1] == 3
    assert any(e[0] == "progress" for e in events)


def test_run_command_failure_raises_a_friendly_error(tmp_path):
    inst = make_installer(tmp_path, [])
    with pytest.raises(core.InstallError, match="código 3"):
        inst._run([sys.executable, "-c", "import sys; sys.exit(3)"])


def test_cancel_terminates_a_running_command(tmp_path):
    inst = make_installer(tmp_path, [])
    timer = threading.Timer(0.5, inst.cancel)
    timer.start()
    with pytest.raises(core.Cancelled):
        inst._run([sys.executable, "-c", "import time; print('x', flush=True); time.sleep(30)"])
    timer.cancel()


def test_pip_progress_never_reaches_one_before_the_end(tmp_path, monkeypatch):
    inst = make_installer(tmp_path, [])
    inst._current = "deps"
    values = []

    def fake_run(args, progress=None, **_):
        if progress:
            for i in range(200):
                values.append(progress("Collecting pkg", i))

    monkeypatch.setattr(inst, "_run", fake_run)
    inst._step_deps()
    assert max(v for v in values if v is not None) < 1.0


def test_gui_files_and_launcher_exist_and_launcher_is_ascii_crlf():
    assert (ROOT / "packaging" / "installer_gui.pyw").is_file()
    raw = (ROOT / "packaging" / "Instalar_DinoTube.bat").read_bytes()
    raw.decode("ascii")
    assert raw.count(b"\r\n") == raw.count(b"\n") and b"installer_gui.pyw" in raw and b"winget" in raw


def test_gui_script_is_valid_python():
    import ast

    ast.parse((ROOT / "packaging" / "installer_gui.pyw").read_text(encoding="utf-8"))
