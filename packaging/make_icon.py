"""Gera packaging/dinotube.ico a partir do mesmo desenho usado como ícone da janela. Uso: python packaging/make_icon.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QGuiApplication  # noqa: E402

from app.styles import app_icon  # noqa: E402


def main():
    QGuiApplication.instance() or QGuiApplication(sys.argv[:1] + ["-platform", "offscreen"])
    target = ROOT / "packaging" / "dinotube.ico"
    if not app_icon.render(256).save(str(target), "ICO"):
        raise SystemExit("Não foi possível gravar o .ico (plugin de imagem ICO ausente).")
    print(f"Ícone gravado em {target}")


if __name__ == "__main__":
    main()
