import os
import threading
from pytubefix import YouTube
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from PIL import Image, ImageTk, ImageSequence
import sys
import subprocess
import re

PASTA_VIDEOS = None

# ---------- Determinar caminho do ffmpeg ----------
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(__file__)

FFMPEG_PATH = os.path.join(base_path, "ffmpeg", "bin", "ffmpeg.exe")
FFMPEG_PATH = os.path.normpath(FFMPEG_PATH)

# ---------- Funções utilitárias ----------
def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "_", name)

# ---------- Spinner ----------
spinner_running = False

def start_spinner():
    global spinner_running
    spinner_running = True
    spinner_frame_container.update_idletasks()
    width = spinner_label.winfo_reqwidth() + label_progresso.winfo_reqwidth() + 20
    height = max(spinner_label.winfo_reqheight(), label_progresso.winfo_reqheight()) + 10
    spinner_frame_container.place(x=central_x(width), y=300, width=width, height=height)
    spinner_frame_container.config(bg="white", bd=1, relief="solid")
    animate()

def stop_spinner():
    global spinner_running
    spinner_running = False
    spinner_frame_container.place_forget()
    label_progresso.config(text="Concluído!")

def animate(counter=0):
    if spinner_running:
        frame = spinner_frames[counter]
        spinner_label.config(image=frame)
        root.after(100, animate, (counter + 1) % len(spinner_frames))

def progresso(stream, chunk, bytes_restantes):
    tamanho_total = stream.filesize
    bytes_baixados = tamanho_total - bytes_restantes
    porcentagem = int(bytes_baixados * 100 / tamanho_total)
    label_progresso.config(text=f"{porcentagem}%")
    root.update_idletasks()

# ---------- Função segura para merge ----------
def merge_video_audio(video_path, audio_path, pasta, title):
    output_file = os.path.join(pasta, sanitize_filename(title) + ".mp4")
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-err_detect", "ignore_err",
        output_file
    ]
    subprocess.run(cmd, check=True)
    return output_file

# ---------- Download vídeo ----------
def baixar_video_thread(url, pasta, resolucao):
    try:
        os.makedirs(pasta, exist_ok=True)
        yt = YouTube(url, on_progress_callback=progresso)
        messagebox.showinfo("Download", f"Iniciando download de:\n{yt.title}")
        start_spinner()

        stream = yt.streams.filter(res=resolucao, progressive=True, file_extension="mp4").first()
        if stream:
            stream.download(output_path=pasta)
        else:
            video_stream = yt.streams.filter(res=resolucao, adaptive=True, only_video=True, file_extension="mp4").first()
            audio_stream = yt.streams.filter(only_audio=True, file_extension="mp4").order_by("abr").desc().first()
            if video_stream and audio_stream:
                video_path = video_stream.download(output_path=pasta)
                audio_path = audio_stream.download(output_path=pasta)
                merge_video_audio(video_path, audio_path, pasta, yt.title)
                os.remove(video_path)
                os.remove(audio_path)

        stop_spinner()
        messagebox.showinfo("Concluído", f"✅ Download concluído!\nSalvo em:\n{pasta}")
    except Exception as e:
        stop_spinner()
        label_progresso.config(text="0%")
        messagebox.showerror("Erro", f"Ocorreu um erro: {e}")

# ---------- Selecionar pasta ----------
def selecionar_pasta():
    global PASTA_VIDEOS
    pasta = filedialog.askdirectory(title="Selecione a pasta para salvar o vídeo")
    if pasta:
        PASTA_VIDEOS = pasta

# ---------- Carregar resoluções ----------
def carregar_resolucoes():
    url = entrada_url.get().strip()
    if not url:
        messagebox.showwarning("Aviso", "Insira a URL primeiro.")
        return
    try:
        yt = YouTube(url)
        resolucoes = sorted({s.resolution for s in yt.streams.filter(file_extension="mp4") if s.resolution},
                            key=lambda x: int(x.replace("p","")))
        combo_resolucoes['values'] = resolucoes
        if resolucoes:
            combo_resolucoes.current(0)
    except Exception as e:
        messagebox.showerror("Erro", f"Falha ao obter resoluções: {e}")

# ---------- Iniciar download ----------
def iniciar_download():
    url = entrada_url.get().strip()
    if not url:
        messagebox.showwarning("Aviso", "Por favor, insira a URL do vídeo.")
        return
    if not PASTA_VIDEOS:
        messagebox.showwarning("Aviso", "Por favor, selecione uma pasta.")
        return
    resolucao = combo_resolucoes.get()
    if not resolucao:
        messagebox.showwarning("Aviso", "Escolha uma resolução.")
        return
    threading.Thread(target=baixar_video_thread, args=(url, PASTA_VIDEOS, resolucao), daemon=True).start()

# ---------- Interface ----------
root = tk.Tk()
root.title("YouTube Downloader")
WIDTH, HEIGHT = 530, 520
root.geometry(f"{WIDTH}x{HEIGHT}")
root.resizable(False, False)

# ---------- Fundo ----------
bg_image = Image.open(os.path.join(base_path, "amelie-poster.png")).convert("RGBA")
bg_image = bg_image.resize((WIDTH, HEIGHT))
alpha = bg_image.split()[3]
alpha = alpha.point(lambda p: p*0.5)
bg_image.putalpha(alpha)
bg_photo = ImageTk.PhotoImage(bg_image)
tk.Label(root, image=bg_photo).place(x=0, y=0, relwidth=1, relheight=1)

def central_x(widget_width):
    return (WIDTH - widget_width)//2

# ---------- URL ----------
frame_url = tk.Frame(root, bg="white", bd=1, relief="solid")
frame_url.place(x=central_x(WIDTH-40), y=20, width=WIDTH-40, height=70)
tk.Label(frame_url, text="URL do vídeo do YouTube:", font=("Segoe UI", 11), bg="white").pack(pady=(5,0))
entrada_url = tk.Entry(frame_url, width=50, font=("Segoe UI", 10))
entrada_url.pack(pady=5)

# ---------- Botões ----------
tk.Button(root, text="Selecionar pasta", font=("Segoe UI", 10), bg="#0078D7", fg="white", command=selecionar_pasta).place(x=central_x(120), y=110)
tk.Button(root, text="Carregar resoluções", font=("Segoe UI", 10), bg="#28A745", fg="white", command=carregar_resolucoes).place(x=central_x(150), y=150)

# ---------- Combobox resoluções ---------
combo_resolucoes = ttk.Combobox(root, state="readonly", width=15)
combo_resolucoes.place(x=central_x(110), y=200)

# ---------- Botão baixar ----------
tk.Button(root, text="Baixar", font=("Segoe UI", 11), bg="#0078D7", fg="white", command=iniciar_download).place(x=central_x(100), y=230)

# ---------- Spinner ----------
spinner_frame_container = tk.Frame(root)
spinner_frame_container.place(x=0, y=0)
spinner_label = tk.Label(spinner_frame_container, bg="white")
spinner_label.pack(side="left", padx=5, pady=5)
label_progresso = tk.Label(spinner_frame_container, text="", font=("Segoe UI", 11), bg="white")
label_progresso.pack(side="left", padx=5, pady=5)

spinner_gif = Image.open(os.path.join(base_path, "spinner.gif"))
spinner_frames = [ImageTk.PhotoImage(f.copy().convert("RGBA").resize((32,32))) for f in ImageSequence.Iterator(spinner_gif)]

root.mainloop()
