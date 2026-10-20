"""Instalador gráfico do DinoTube: escolhe a pasta de instalação, mostra cada etapa e a barra de progresso, e no fim
oferece abrir o programa. Dê duplo clique neste arquivo (ou use Instalar_DinoTube.bat). Precisa do Python com Tk."""

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _fatal(message):
    """Sem Tk não há janela: no Windows, uma caixa de mensagem do sistema; nos outros, o terminal."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, "Instalador do DinoTube", 0x10)
            return
        except Exception:
            pass
    print(message, file=sys.stderr)


try:
    import tkinter as tk
    from tkinter import filedialog, ttk
except ImportError:  # Python instalado sem o Tcl/Tk
    _fatal("Este Python foi instalado sem o Tcl/Tk, que o instalador usa para desenhar a janela.\n\n"
           "Reinstale o Python (python.org) mantendo marcada a opção \"tcl/tk and IDLE\", ou rode "
           "packaging\\build_windows.bat.")
    raise SystemExit(1)

import installer_core as core  # noqa: E402

BG, PANEL, ELEVATED = "#111318", "#191C23", "#222631"
TEXT, MUTED = "#F2F4F8", "#A9B0BE"
ACCENT, ACCENT_HOVER, ACCENT_SOFT = "#8B7CF6", "#9D90F8", "#2A2650"
OK, ERROR, BORDER = "#42B883", "#E06C75", "#303642"
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 20, "bold")
GLYPH = {core.PENDING: "○", core.RUNNING: "●", core.DONE: "✔", core.FAILED: "✖", core.SKIPPED: "–"}
GLYPH_COLOR = {core.PENDING: MUTED, core.RUNNING: ACCENT, core.DONE: OK, core.FAILED: ERROR, core.SKIPPED: MUTED}
PHASES = ("Pasta", "Instalação", "Concluído")


class Button(tk.Label):
    """Botão chato e arredondado visualmente (Label com realce ao passar o mouse); 'primary' usa a cor de destaque."""

    def __init__(self, master, text, command, primary=False, width=14):
        self._primary = primary
        super().__init__(master, text=text, font=FONT_BOLD, width=width, pady=8, cursor="hand2",
                         bg=ACCENT if primary else ELEVATED, fg="#10131A" if primary else TEXT)
        self._command = command
        self._enabled = True
        self.bind("<Button-1>", lambda _e: self._enabled and self._command())
        self.bind("<Enter>", lambda _e: self._paint(True))
        self.bind("<Leave>", lambda _e: self._paint(False))

    def _paint(self, hover):
        if not self._enabled:
            self.configure(bg=ELEVATED, fg=MUTED, cursor="arrow")
        elif self._primary:
            self.configure(bg=ACCENT_HOVER if hover else ACCENT, fg="#10131A", cursor="hand2")
        else:
            self.configure(bg=BORDER if hover else ELEVATED, fg=TEXT, cursor="hand2")

    def set_enabled(self, enabled):
        self._enabled = enabled
        self._paint(False)


class InstallerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Instalador do DinoTube")
        self.configure(bg=BG)
        self.resizable(False, False)
        icon = HERE / "dinotube.ico"
        if icon.is_file():
            try:
                self.iconbitmap(default=str(icon))
            except tk.TclError:
                pass
        width, height = 760, 560
        x, y = (self.winfo_screenwidth() - width) // 2, (self.winfo_screenheight() - height) // 3
        self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.events = queue.Queue()
        self.installer = None
        self.thread = None
        self.result = None
        self.log_visible = False
        self.step_labels = {}
        self.exe_path = None

        self.path_var = tk.StringVar(value=core.default_install_dir())
        self.desktop_var = tk.BooleanVar(value=True)
        self.menu_var = tk.BooleanVar(value=True)
        self.launch_var = tk.BooleanVar(value=True)

        self._build_side()
        self.content = tk.Frame(self, bg=BG)
        self.content.pack(side="right", fill="both", expand=True, padx=28, pady=24)
        self._style()
        self.show_welcome()
        self.after(100, self._poll)

    # -- estrutura
    def _style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Dino.Horizontal.TProgressbar", troughcolor=ELEVATED, background=ACCENT, bordercolor=ELEVATED,
                        lightcolor=ACCENT, darkcolor=ACCENT, thickness=14)

    def _build_side(self):
        side = tk.Frame(self, bg=PANEL, width=210)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        logo = tk.Canvas(side, width=72, height=72, bg=PANEL, highlightthickness=0)
        logo.pack(anchor="w", padx=24, pady=(28, 6))
        logo.create_oval(2, 2, 70, 70, fill=ACCENT, outline="")
        logo.create_polygon(28, 22, 28, 50, 52, 36, fill="#10131A", outline="")
        tk.Label(side, text="DinoTube", font=("Segoe UI", 16, "bold"), bg=PANEL, fg=TEXT).pack(anchor="w", padx=24)
        tk.Label(side, text=f"versão {core.app_version()}", font=FONT, bg=PANEL, fg=MUTED).pack(anchor="w", padx=24)
        self.phase_labels = []
        box = tk.Frame(side, bg=PANEL)
        box.pack(anchor="w", padx=24, pady=(36, 0))
        for index, name in enumerate(PHASES, start=1):
            label = tk.Label(box, text=f"{index}   {name}", font=FONT, bg=PANEL, fg=MUTED, anchor="w")
            label.pack(anchor="w", pady=5)
            self.phase_labels.append(label)

    def _phase(self, index):
        for i, label in enumerate(self.phase_labels):
            label.configure(fg=ACCENT_HOVER if i == index else (TEXT if i < index else MUTED),
                            font=FONT_BOLD if i == index else FONT)

    def _drop_trace(self):
        trace = getattr(self, "_trace", None)
        if trace is not None:
            self.path_var.trace_remove("write", trace)
            self._trace = None

    def _clear(self):
        self._drop_trace()  # o campo da página anterior some; sem isso o aviso tentaria escrever num widget destruído
        for child in self.content.winfo_children():
            child.destroy()

    def _heading(self, title, subtitle):
        tk.Label(self.content, text=title, font=FONT_TITLE, bg=BG, fg=TEXT, anchor="w").pack(fill="x")
        tk.Label(self.content, text=subtitle, font=FONT, bg=BG, fg=MUTED, anchor="w", justify="left", wraplength=470).pack(
            fill="x", pady=(4, 14))

    def _buttons(self):
        bar = tk.Frame(self.content, bg=BG)
        bar.pack(side="bottom", fill="x", pady=(14, 0))
        return bar

    # -- página 1: pasta
    def show_welcome(self):
        self._clear()
        self._phase(0)
        self._heading("Instalar o DinoTube", "Escolha a pasta onde o programa será instalado. Tudo é preparado automaticamente; "
                      "a primeira instalação baixa os componentes necessários e leva alguns minutos.")
        tk.Label(self.content, text="Pasta de instalação", font=FONT_BOLD, bg=BG, fg=TEXT, anchor="w").pack(fill="x")
        row = tk.Frame(self.content, bg=BG)
        row.pack(fill="x", pady=(6, 0))
        entry = tk.Entry(row, textvariable=self.path_var, font=FONT, bg=ELEVATED, fg=TEXT, insertbackground=TEXT,
                         relief="flat", highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
        entry.pack(side="left", fill="x", expand=True, ipady=7)
        Button(row, "Procurar...", self._browse, width=11).pack(side="left", padx=(8, 0))
        self.path_message = tk.Label(self.content, text="", font=FONT, bg=BG, fg=ERROR, anchor="w", justify="left", wraplength=470)
        self.path_message.pack(fill="x", pady=(6, 8))
        self._drop_trace()
        self._trace = self.path_var.trace_add("write", lambda *_: self._validate())

        for text, var in (("Criar um atalho na Área de Trabalho", self.desktop_var),
                          ("Criar um atalho no Menu Iniciar", self.menu_var)):
            self._check(text, var)

        space = tk.Label(self.content, text="Espaço necessário: cerca de 4 GB durante a instalação (1,5 GB depois dela).",
                         font=("Segoe UI", 9), bg=BG, fg=MUTED, anchor="w")
        space.pack(fill="x", pady=(10, 0))

        bar = self._buttons()
        self.install_button = Button(bar, "Instalar", self._start, primary=True)
        self.install_button.pack(side="right")
        Button(bar, "Cancelar", self._on_close).pack(side="right", padx=(0, 8))
        self._validate()
        entry.focus_set()

    def _check(self, text, var):
        check = tk.Checkbutton(self.content, text=text, variable=var, font=FONT, bg=BG, fg=TEXT, activebackground=BG,
                               activeforeground=TEXT, selectcolor=ELEVATED, anchor="w", highlightthickness=0)
        check.pack(fill="x", pady=2)

    def _browse(self):
        start = self.path_var.get() if Path(self.path_var.get()).exists() else str(Path.home())
        chosen = filedialog.askdirectory(title="Escolha a pasta de instalação", initialdir=start, mustexist=False)
        if chosen:
            chosen = str(Path(chosen))
            self.path_var.set(chosen if Path(chosen).name.lower() == "dinotube" else str(Path(chosen) / "DinoTube"))

    def _validate(self):
        ok, message = core.validate_install_dir(self.path_var.get())
        self.path_message.configure(text=message)
        self.install_button.set_enabled(ok)
        return ok

    # -- página 2: progresso
    def _start(self):
        if not self._validate():
            return
        self._clear()
        self._phase(1)
        self._heading("Instalando...", "Pode deixar esta janela aberta. Nenhuma outra ação é necessária.")
        steps = tk.Frame(self.content, bg=BG)
        steps.pack(fill="x")
        self.step_labels = {}
        for step in core.STEPS:
            line = tk.Frame(steps, bg=BG)
            line.pack(fill="x", pady=1)
            glyph = tk.Label(line, text=GLYPH[core.PENDING], font=FONT_BOLD, bg=BG, fg=GLYPH_COLOR[core.PENDING], width=2)
            glyph.pack(side="left")
            title = tk.Label(line, text=step.title, font=FONT, bg=BG, fg=MUTED, anchor="w")
            title.pack(side="left")
            self.step_labels[step.key] = (glyph, title)

        self.percent = tk.Label(self.content, text="0%", font=FONT_BOLD, bg=BG, fg=TEXT, anchor="e")
        self.percent.pack(fill="x", pady=(16, 2))
        self.bar = ttk.Progressbar(self.content, style="Dino.Horizontal.TProgressbar", maximum=1000, mode="determinate")
        self.bar.pack(fill="x")
        self.current = tk.Label(self.content, text="", font=("Segoe UI", 9), bg=BG, fg=MUTED, anchor="w")
        self.current.pack(fill="x", pady=(4, 0))

        self.details_button = tk.Label(self.content, text="▸ Mostrar detalhes", font=("Segoe UI", 9), bg=BG, fg=ACCENT_HOVER,
                                       cursor="hand2", anchor="w")
        self.details_button.pack(fill="x", pady=(8, 0))
        self.details_button.bind("<Button-1>", lambda _e: self._toggle_log())
        self.log_frame = tk.Frame(self.content, bg=BG)
        self.log = tk.Text(self.log_frame, height=6, font=("Consolas", 8), bg=PANEL, fg=MUTED, relief="flat", wrap="none",
                           state="disabled", highlightthickness=0)
        self.log.pack(fill="both", expand=True)
        self.log_visible = False

        bar = self._buttons()
        self.cancel_button = Button(bar, "Cancelar", self._cancel)
        self.cancel_button.pack(side="right")

        self.installer = core.Installer(self.path_var.get().strip().strip('"'), self.desktop_var.get(), self.menu_var.get(),
                                        on_event=lambda *event: self.events.put(event))
        self.thread = threading.Thread(target=self._work, daemon=True)
        self.thread.start()

    def _work(self):
        self.events.put(("finished", *self.installer.run()))

    def _toggle_log(self):
        self.log_visible = not self.log_visible
        if self.log_visible:
            self.log_frame.pack(fill="both", expand=True, pady=(4, 0))
            self.details_button.configure(text="▾ Ocultar detalhes")
        else:
            self.log_frame.pack_forget()
            self.details_button.configure(text="▸ Mostrar detalhes")

    def _cancel(self):
        if self.installer is not None and self.thread is not None and self.thread.is_alive():
            self.cancel_button.set_enabled(False)
            self.current.configure(text="Cancelando...")
            self.installer.cancel()

    def _poll(self):
        try:
            while True:
                self._handle(self.events.get_nowait())
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _handle(self, event):
        kind = event[0]
        if kind == "step":
            _, key, state = event
            glyph, title = self.step_labels[key]
            glyph.configure(text=GLYPH[state], fg=GLYPH_COLOR[state])
            title.configure(fg=TEXT if state in (core.RUNNING, core.DONE) else (ERROR if state == core.FAILED else MUTED),
                            font=FONT_BOLD if state == core.RUNNING else FONT)
            if state == core.RUNNING:
                self.current.configure(text=next(s.title for s in core.STEPS if s.key == key) + "...")
        elif kind == "progress":
            value = event[1]
            self.bar["value"] = int(value * 1000)
            self.percent.configure(text=f"{int(value * 100)}%")
        elif kind == "log":
            self.log.configure(state="normal")
            self.log.insert("end", event[1] + "\n")
            self.log.see("end")
            self.log.configure(state="disabled")
        elif kind == "finished":
            self.result = event[1:]
            self.show_finished(*self.result)

    # -- página 3: fim
    def show_finished(self, status, detail):
        self._clear()
        self._phase(2)
        if status == "ok":
            self.exe_path = detail
            self._heading("Tudo pronto!", "O DinoTube foi instalado com sucesso.")
            tk.Label(self.content, text="Instalado em", font=FONT_BOLD, bg=BG, fg=TEXT, anchor="w").pack(fill="x")
            tk.Label(self.content, text=str(Path(detail).parent), font=FONT, bg=BG, fg=MUTED, anchor="w", wraplength=470,
                     justify="left").pack(fill="x", pady=(2, 12))
            self._check("Abrir o DinoTube ao concluir", self.launch_var)
            bar = self._buttons()
            Button(bar, "Concluir", self._finish, primary=True).pack(side="right")
            Button(bar, "Abrir a pasta", self._open_folder).pack(side="right", padx=(0, 8))
        elif status == "cancelled":
            self._heading("Instalação cancelada", "Nada foi instalado. Você pode tentar de novo quando quiser.")
            bar = self._buttons()
            Button(bar, "Fechar", self.destroy).pack(side="right")
            Button(bar, "Voltar", self.show_welcome, primary=True).pack(side="right", padx=(0, 8))
        else:
            self._heading("Não foi possível instalar", detail)
            tk.Label(self.content, text=f"O registro completo está em:\n{core.ROOT / 'packaging' / 'build.log'}", font=("Segoe UI", 9),
                     bg=BG, fg=MUTED, anchor="w", justify="left").pack(fill="x")
            bar = self._buttons()
            Button(bar, "Fechar", self.destroy).pack(side="right")
            Button(bar, "Ver registro", self._open_log).pack(side="right", padx=(0, 8))
            Button(bar, "Tentar de novo", self.show_welcome, primary=True).pack(side="right", padx=(0, 8))

    def _open_folder(self):
        self._open(Path(self.exe_path).parent)

    def _open_log(self):
        self._open(core.ROOT / "packaging" / "build.log")

    @staticmethod
    def _open(path):
        try:
            if sys.platform == "win32":
                os.startfile(str(path))  # noqa: S606
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError:
            pass

    def _finish(self):
        if self.launch_var.get() and self.exe_path and sys.platform == "win32":
            try:
                subprocess.Popen([self.exe_path], cwd=str(Path(self.exe_path).parent))
            except OSError:
                pass
        self.destroy()

    def _on_close(self):
        if self.thread is not None and self.thread.is_alive():
            self._cancel()
            return
        self.destroy()


def main():
    InstallerApp().mainloop()


if __name__ == "__main__":
    main()
