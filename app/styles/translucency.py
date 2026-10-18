"""Janela translúcida do tema Vidro cinza: deixa ver (borrado) o que está aberto por trás do aplicativo.

Duas partes:
  * o Qt precisa de uma janela com fundo translúcido (`WA_TranslucentBackground`); isso só pode mudar com a janela
    escondida, por isso a troca esconde e mostra de novo;
  * o desfoque do que está atrás é do sistema operacional. No Windows (10 1803+ e 11) ele é pedido pelo acrílico do DWM.
    Em outros sistemas a janela fica apenas transparente, sem desfoque (o Qt não tem como desfocar o que é de outra janela)."""

import sys

from PySide6.QtCore import Qt

ACCENT_DISABLED, ACCENT_BLURBEHIND, ACCENT_ACRYLIC = 0, 3, 4
WCA_ACCENT_POLICY = 19


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


def _accent(hwnd, state, tint):
    """SetWindowCompositionAttribute com uma política de 'accent' (acrílico, desfoque simples ou nenhum)."""
    import ctypes
    from ctypes import POINTER, Structure, byref, c_int, c_size_t, c_uint, c_void_p, sizeof

    class AccentPolicy(Structure):
        _fields_ = [("state", c_int), ("flags", c_int), ("tint", c_uint), ("animation", c_int)]

    class CompositionData(Structure):
        _fields_ = [("attribute", c_int), ("data", c_void_p), ("size", c_size_t)]

    policy = AccentPolicy(state, 2 if state else 0, tint, 0)
    data = CompositionData(WCA_ACCENT_POLICY, ctypes.cast(byref(policy), c_void_p), sizeof(policy))
    set_attribute = ctypes.windll.user32.SetWindowCompositionAttribute
    set_attribute.argtypes = [c_void_p, POINTER(CompositionData)]
    return bool(set_attribute(c_void_p(hwnd), byref(data)))


def _dwm_backdrop(hwnd, on):
    """Windows 11 22H2+: material acrílico do sistema no lugar do fundo da janela."""
    import ctypes
    from ctypes import byref, c_int

    class Margins(ctypes.Structure):
        _fields_ = [("l", c_int), ("r", c_int), ("t", c_int), ("b", c_int)]

    dwm = ctypes.windll.dwmapi
    dwm.DwmExtendFrameIntoClientArea(hwnd, byref(Margins(-1, -1, -1, -1) if on else Margins(0, 0, 0, 0)))
    dwm.DwmSetWindowAttribute(hwnd, 20, byref(c_int(1 if on else 0)), 4)  # DWMWA_USE_IMMERSIVE_DARK_MODE
    return dwm.DwmSetWindowAttribute(hwnd, 38, byref(c_int(3 if on else 1)), 4) == 0  # DWMWA_SYSTEMBACKDROP_TYPE


def enable_system_blur(window, on):
    """Desfoque do que está atrás da janela. Sem efeito, e sem erro, fora do Windows. Devolve True se o sistema aceitou."""
    if not sys.platform.startswith("win"):
        return False
    try:
        hwnd = int(window.winId())
        if not on:
            _accent(hwnd, ACCENT_DISABLED, 0)
            _dwm_backdrop(hwnd, False)
            return True
        # tom quase transparente (ABGR): quem escurece o vidro é o desenho do próprio tema
        if _accent(hwnd, ACCENT_ACRYLIC, 0x14181410):
            return True
        if _dwm_backdrop(hwnd, True):
            return True
        return _accent(hwnd, ACCENT_BLURBEHIND, 0)
    except Exception:  # noqa: BLE001  versão do Windows sem suporte: segue só com a transparência
        return False
