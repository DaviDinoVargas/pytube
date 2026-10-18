"""Janela translúcida do tema Vidro cinza: deixa ver (borrado) o que está aberto por trás do aplicativo.

Duas partes:
  * o Qt precisa de uma janela com fundo translúcido (`WA_TranslucentBackground`); isso só pode mudar com a janela
    escondida, por isso a troca esconde e mostra de novo;
  * o desfoque do que está atrás é do sistema operacional. No Windows (10 1803+ e 11) ele é pedido pelo acrílico do DWM.
    Em outros sistemas a janela fica apenas transparente, sem desfoque (o Qt não tem como desfocar o que é de outra janela)."""

import sys

from PySide6.QtCore import Qt

ACCENT_DISABLED, ACCENT_TRANSPARENT, ACCENT_ACRYLIC = 0, 2, 4
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
        enable_system_blur(window, on, getattr(window, "glass_blur_level", "strong"))
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


def _dwm_backdrop(hwnd, kind):
    """Windows 11 22H2+: material do sistema atrás da janela (1 = nenhum, 3 = acrílico)."""
    import ctypes
    from ctypes import byref, c_int

    class Margins(ctypes.Structure):
        _fields_ = [("l", c_int), ("r", c_int), ("t", c_int), ("b", c_int)]

    dwm = ctypes.windll.dwmapi
    dwm.DwmExtendFrameIntoClientArea(hwnd, byref(Margins(-1, -1, -1, -1) if kind != 1 else Margins(0, 0, 0, 0)))
    dwm.DwmSetWindowAttribute(hwnd, 20, byref(c_int(1)), 4)  # DWMWA_USE_IMMERSIVE_DARK_MODE
    return dwm.DwmSetWindowAttribute(hwnd, 38, byref(c_int(kind)), 4) == 0  # DWMWA_SYSTEMBACKDROP_TYPE


def enable_system_blur(window, on, level="strong"):
    """Transparência e desfoque do que está atrás da janela. `level`: 'strong' (acrílico do Windows, o fosco) ou 'none'
    (transparente, sem desfoque). Fora do Windows não faz nada. Devolve True se o sistema aceitou.

    Só o accent do sistema (SetWindowCompositionAttribute) é usado: estender o vidro do DWM pela janela inteira fazia o
    Windows não limpar o que havia por trás, e o fundo mostrava a tela anterior do aplicativo."""
    if not sys.platform.startswith("win"):
        return False
    try:
        hwnd = int(window.winId())
        if not on:
            return _accent(hwnd, ACCENT_DISABLED, 0)
        if level == "none":
            return _accent(hwnd, ACCENT_TRANSPARENT, 0x00000000)
        # tom quase transparente (ABGR): quem escurece o vidro é o desenho do próprio tema
        if _accent(hwnd, ACCENT_ACRYLIC, 0x14181410):
            return True
        return _dwm_backdrop(hwnd, 3)
    except Exception:  # noqa: BLE001  versão do Windows sem suporte: segue só com a transparência do Qt
        return False
