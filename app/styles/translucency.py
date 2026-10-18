"""Janela translúcida do tema Vidro cinza: deixa ver a área de trabalho por trás.

O Qt só pode mudar isso com a janela escondida (o sistema recria a janela nativa), por isso a troca esconde e mostra de
novo. No Windows 11 o aplicativo também pede ao sistema o desfoque de acrílico atrás da janela; nos demais sistemas
a janela fica transparente (sem desfoque do fundo) e o aspecto fosco vem do grão e do brilho desenhados pelo tema."""

import sys

from PySide6.QtCore import Qt


def set_window_translucent(window, on):
    """Liga ou desliga a translucidez. Devolve True se algo mudou."""
    on = bool(on)
    if window.testAttribute(Qt.WA_TranslucentBackground) == on:
        return False
    visible = window.isVisible()
    if visible:
        window.hide()
    window.setAttribute(Qt.WA_TranslucentBackground, on)
    window.setAutoFillBackground(False)
    if visible:
        window.show()
        enable_system_blur(window, on)
    return True


def enable_system_blur(window, on):
    """Acrílico do Windows 11 (22H2+) atrás da janela. Sem efeito, e sem erro, em qualquer outro sistema."""
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes

        hwnd = int(window.winId())
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20, DWMWA_SYSTEMBACKDROP_TYPE = 38 (1 = nenhum, 3 = acrílico)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1 if on else 0)), 4)
        backdrop = ctypes.c_int(3 if on else 1)
        return ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(backdrop), 4) == 0
    except Exception:  # noqa: BLE001  versão do Windows sem suporte: segue só com a transparência
        return False
