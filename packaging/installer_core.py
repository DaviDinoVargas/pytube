"""Lógica do instalador do DinoTube, sem interface: prepara o ambiente, empacota com o PyInstaller e instala na pasta
escolhida (com atalhos e entrada em "Aplicativos e recursos" do Windows). A tela fica em installer_gui.pyw."""

import os
import re
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "DinoTube"
EXE_NAME = "DinoTube.exe"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\DinoTube"
MIN_PYTHON = (3, 10)
NEED_BUILD_MB = 4000  # ambiente virtual + pastas build/ e dist/ (o PySide6 com o Chromium é grande)
NEED_INSTALL_MB = 1500

IS_WINDOWS = sys.platform == "win32"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass(frozen=True)
class Step:
    key: str
    title: str
    weight: int  # peso aproximado na barra de progresso geral


STEPS = (
    Step("python", "Verificando o Python", 1),
    Step("files", "Conferindo os arquivos do programa", 1),
    Step("env", "Preparando o ambiente de construção", 3),
    Step("deps", "Baixando e instalando as dependências", 30),
    Step("icon", "Gerando o ícone", 1),
    Step("build", "Empacotando o aplicativo", 42),
    Step("install", "Copiando para a pasta de instalação", 10),
    Step("extras", "Criando atalhos e o desinstalador", 3),
)
TOTAL_WEIGHT = sum(s.weight for s in STEPS)

PENDING, RUNNING, DONE, FAILED, SKIPPED = "pending", "running", "done", "failed", "skipped"


class InstallError(Exception):
    """Falha de uma etapa, com uma mensagem que o usuário entende."""


class Cancelled(Exception):
    pass


# -- caminhos e verificações -----------------------------------------------------------------------------------
def default_install_dir():
    if IS_WINDOWS:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return str(Path(base) / "Programs" / APP_NAME)
    return str(Path.home() / APP_NAME)


def app_version():
    match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', (ROOT / "app" / "__init__.py").read_text(encoding="utf-8"))
    return match.group(1) if match else "1.0.0"


def _free_mb(path):
    probe = Path(path)
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return shutil.disk_usage(probe).free // (1024 * 1024)


def validate_install_dir(path, root=ROOT):
    """(ok, mensagem) para a pasta escolhida. A mensagem diz o que corrigir."""
    text = (path or "").strip().strip('"')
    if not text:
        return False, "Escolha a pasta onde o DinoTube será instalado."
    target = Path(text)
    if not target.is_absolute():
        return False, "Digite o caminho completo da pasta (por exemplo C:\\Programas\\DinoTube)."
    try:
        resolved = target.resolve()
        project = Path(root).resolve()
    except OSError:
        return False, "Esse caminho não é válido."
    if resolved == project or project in resolved.parents or resolved in project.parents:
        return False, "Escolha uma pasta fora da pasta do projeto."
    if resolved.parent == resolved:
        return False, "Escolha uma pasta, não a raiz do disco."
    if resolved.exists() and not resolved.is_dir():
        return False, "Já existe um arquivo com esse nome."
    if resolved.exists() and any(resolved.iterdir()) and not (resolved / EXE_NAME).exists():
        return False, "A pasta já tem outros arquivos. Escolha uma pasta vazia ou uma nova (ex.: ...\\DinoTube)."
    if _free_mb(resolved) < NEED_INSTALL_MB:
        return False, f"Pouco espaço livre nesse disco (precisa de cerca de {NEED_INSTALL_MB / 1000:.1f} GB)."
    return True, ""


def build_space_ok(root=ROOT):
    return _free_mb(root) >= NEED_BUILD_MB


def python_ok():
    return sys.version_info[:2] >= MIN_PYTHON


def ffmpeg_ok(root=ROOT):
    bin_dir = Path(root) / "third_party" / "ffmpeg" / "bin"
    return (bin_dir / "ffmpeg.exe").is_file() and (bin_dir / "ffprobe.exe").is_file()


# -- scripts gerados -------------------------------------------------------------------------------------------
def _ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def shortcut_script(exe, links):
    """PowerShell que cria atalhos (.lnk) para `exe`. `links`: lista de caminhos .lnk."""
    lines = ["$shell = New-Object -ComObject WScript.Shell"]
    for link in links:
        lines += [
            f"New-Item -ItemType Directory -Force -Path (Split-Path {_ps_quote(link)}) | Out-Null",
            f"$s = $shell.CreateShortcut({_ps_quote(link)})",
            f"$s.TargetPath = {_ps_quote(exe)}",
            f"$s.WorkingDirectory = {_ps_quote(Path(exe).parent)}",
            f"$s.IconLocation = {_ps_quote(str(exe) + ',0')}",
            f"$s.Description = {_ps_quote(APP_NAME)}",
            "$s.Save()",
        ]
    return "\n".join(lines)


def uninstall_batch(install_dir, links):
    """Desinstalador sem Python: confirma, apaga atalhos, a entrada do Windows e a pasta (depois de fechar)."""
    deletes = "\r\n".join(f'del /f /q "{link}" >nul 2>&1' for link in links)
    return (
        "@echo off\r\n"
        "setlocal\r\n"
        f'set "APPDIR={install_dir}"\r\n'
        "powershell -NoProfile -Command \"Add-Type -AssemblyName PresentationFramework; "
        "$r = [System.Windows.MessageBox]::Show('Remover o DinoTube deste computador? "
        "Seus videos e a biblioteca nao serao apagados.', 'Desinstalar o DinoTube', 'YesNo', 'Question'); "
        "if ($r -ne 'Yes') { exit 1 }\"\r\n"
        "if errorlevel 1 exit /b 0\r\n"
        f"taskkill /f /im {EXE_NAME} >nul 2>&1\r\n"
        f"{deletes}\r\n"
        f'reg delete "HKCU\\{UNINSTALL_KEY}" /f >nul 2>&1\r\n'
        'start "" /min cmd /c "ping -n 3 127.0.0.1 >nul & rmdir /s /q "%APPDIR%""\r\n'
        "exit /b 0\r\n"
    )


# -- execução ------------------------------------------------------------------------------------------------------
class Installer:
    """Roda as etapas. `on_event(kind, *args)` recebe: ('step', key, estado), ('progress', 0..1), ('log', linha)."""

    def __init__(self, install_dir, desktop=True, start_menu=True, on_event=None, root=ROOT, python=None):
        self.install_dir = Path(install_dir)
        self.desktop, self.start_menu = desktop, start_menu
        self._emit = on_event or (lambda *_: None)
        self.root = Path(root)
        self.python = python or sys.executable
        self.venv = self.root / ".venv-build"
        self.venv_python = self.venv / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")
        self.log_path = self.root / "packaging" / "build.log"
        self._cancel = threading.Event()
        self._process = None
        self._done_weight = 0
        self._current = None
        self.links = []

    # -- infraestrutura
    def cancel(self):
        self._cancel.set()
        process = self._process
        if process is not None and process.poll() is None:
            process.terminate()

    def _check_cancel(self):
        if self._cancel.is_set():
            raise Cancelled()

    def _log(self, line):
        self._emit("log", line)
        try:
            with open(self.log_path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass

    def _progress(self, fraction):
        weight = next((s.weight for s in STEPS if s.key == self._current), 0)
        total = self._done_weight + weight * max(0.0, min(1.0, fraction))
        self._emit("progress", total / TOTAL_WEIGHT)

    def _run(self, args, progress=None, cwd=None, env=None):
        """Executa um comando mostrando a saída; `progress(linha, n)` devolve 0..1 ou None."""
        self._log("$ " + " ".join(str(a) for a in args))
        process = subprocess.Popen(
            [str(a) for a in args], cwd=str(cwd or self.root), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW,
        )
        self._process = process
        count = 0
        for raw in process.stdout:
            line = raw.rstrip()
            if line:
                count += 1
                self._log(line)
                if progress:
                    value = progress(line, count)
                    if value is not None:
                        self._progress(value)
            if self._cancel.is_set():
                process.terminate()
        code = process.wait()
        self._process = None
        self._check_cancel()
        if code != 0:
            raise InstallError(f"O comando terminou com erro (código {code}). Veja os detalhes no registro.")

    # -- etapas
    def run(self):
        """Executa tudo. Devolve ('ok', caminho_do_exe) | ('cancelled', None) | ('error', mensagem)."""
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_path.write_text("", encoding="utf-8")
        except OSError:
            pass
        for step in STEPS:
            self._current = step.key
            self._emit("step", step.key, RUNNING)
            self._progress(0.0)
            try:
                self._check_cancel()
                getattr(self, f"_step_{step.key}")()
            except Cancelled:
                self._emit("step", step.key, FAILED)
                return "cancelled", None
            except InstallError as exc:
                self._emit("step", step.key, FAILED)
                self._log(f"ERRO: {exc}")
                return "error", str(exc)
            except Exception as exc:  # noqa: BLE001  qualquer falha inesperada vira uma mensagem, nunca uma tela travada
                self._emit("step", step.key, FAILED)
                self._log(f"ERRO inesperado: {exc!r}")
                return "error", f"Erro inesperado: {exc}"
            self._emit("step", step.key, DONE)
            self._done_weight += step.weight
            self._progress(0.0)
        self._emit("progress", 1.0)
        return "ok", str(self.install_dir / EXE_NAME)

    def _step_python(self):
        if not python_ok():
            raise InstallError(f"É preciso o Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} ou mais novo (este é o {sys.version.split()[0]}).")
        self._log(f"Python {sys.version.split()[0]} em {self.python}")
        if not build_space_ok(self.root):
            raise InstallError(f"Pouco espaço livre no disco do projeto (precisa de cerca de {NEED_BUILD_MB / 1000:.0f} GB).")

    def _step_files(self):
        if not ffmpeg_ok(self.root):
            raise InstallError("Faltam third_party\\ffmpeg\\bin\\ffmpeg.exe e ffprobe.exe. Baixe o projeto completo (git clone ou o ZIP inteiro).")
        for name in ("DinoTube.spec", "main.py", "requirements.txt"):
            if not (self.root / name).is_file():
                raise InstallError(f"Arquivo do projeto não encontrado: {name}")

    def _step_env(self):
        if not self.venv_python.exists():
            self._run([self.python, "-m", "venv", self.venv])
        if not self.venv_python.exists():
            raise InstallError("Não consegui criar o ambiente virtual do Python.")

    def _step_deps(self):
        expected = 70  # linhas "Collecting/Downloading/Installing" de uma instalação completa

        def parse(line, _n):
            if line.startswith(("Collecting", "Downloading", "Using cached", "Installing collected", "Successfully installed")):
                parse.seen += 1
            return min(0.97, parse.seen / expected)

        parse.seen = 0
        self._run([self.venv_python, "-m", "pip", "install", "--upgrade", "pip"])
        self._run([self.venv_python, "-m", "pip", "install", "-r", "requirements.txt", "pyinstaller"], progress=parse)

    def _step_icon(self):
        self._run([self.venv_python, "packaging/make_icon.py"])

    def _step_build(self):
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True, creationflags=NO_WINDOW)
        stages = (("Building COLLECT", 0.9), ("Building EXE", 0.8), ("Building PKG", 0.7), ("Building PYZ", 0.55))

        def parse(line, n):
            for marker, value in stages:
                if marker in line:
                    return value
            return min(0.5, n / 600)

        self._run([self.venv_python, "-m", "PyInstaller", "DinoTube.spec", "--noconfirm", "--clean"], progress=parse)
        if not (self.root / "dist" / APP_NAME / EXE_NAME).is_file():
            raise InstallError("O empacotamento terminou, mas o DinoTube.exe não foi gerado. Veja o registro.")

    def _step_install(self):
        source = self.root / "dist" / APP_NAME
        target = self.install_dir
        ok, message = validate_install_dir(str(target), self.root)
        if not ok:
            raise InstallError(message)
        files = [p for p in source.rglob("*") if p.is_file()]
        total = max(1, sum(p.stat().st_size for p in files))
        if target.exists():
            self._log(f"Substituindo a instalação anterior em {target}")
            shutil.rmtree(target, ignore_errors=True)
        copied = 0
        for path in files:
            self._check_cancel()
            destination = target / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            copied += path.stat().st_size
            self._progress(copied / total)
        self._log(f"{len(files)} arquivos copiados para {target}")

    def _step_extras(self):
        exe = self.install_dir / EXE_NAME
        self.links = []
        if self.desktop:
            self.links.append(Path(self._known_folder("Desktop")) / f"{APP_NAME}.lnk")
        if self.start_menu:
            self.links.append(Path(os.environ.get("APPDATA", str(Path.home()))) / "Microsoft" / "Windows" / "Start Menu"
                              / "Programs" / f"{APP_NAME}.lnk")
        uninstaller = self.install_dir / "Desinstalar.bat"
        menu_links = [str(link) for link in self.links]
        uninstaller.write_bytes(uninstall_batch(str(self.install_dir), menu_links).encode("ascii", "replace"))
        if not IS_WINDOWS:
            self._log("Atalhos e registro do Windows ignorados (não é Windows).")
            return
        if self.links:
            self._run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                       shortcut_script(exe, [str(link) for link in self.links])])
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
            for name, value in (
                ("DisplayName", APP_NAME), ("DisplayVersion", app_version()), ("Publisher", APP_NAME),
                ("InstallLocation", str(self.install_dir)), ("DisplayIcon", str(exe)),
                ("UninstallString", f'cmd /c "{uninstaller}"'),
            ):
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)

    @staticmethod
    def _known_folder(name):
        if IS_WINDOWS:
            try:
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", f"[Environment]::GetFolderPath('{name}')"],
                    capture_output=True, text=True, creationflags=NO_WINDOW, timeout=20,
                )
                folder = result.stdout.strip()
                if folder:
                    return folder
            except (OSError, subprocess.SubprocessError):
                pass
        return str(Path.home() / name)
