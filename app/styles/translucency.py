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
        enable_system_blur(window, on, getattr(window, "glass_blur_level", "light"))
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


def _extend_frame(hwnd):
    """Estende o vidro do DWM por toda a janela: é isso que faz o Windows respeitar o alfa do que o Qt desenha na área
    útil. Sem isso (ou se for zerado depois) a janela sai opaca, mesmo com WA_TranslucentBackground."""
    import ctypes
    from ctypes import byref, c_int

    class Margins(ctypes.Structure):
        _fields_ = [("l", c_int), ("r", c_int), ("t", c_int), ("b", c_int)]

    return ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, byref(Margins(-1, -1, -1, -1))) == 0


def _dwm_backdrop(hwnd, kind):
    """Windows 11 22H2+: material do sistema atrás da janela (1 = nenhum, 2 = Mica, 3 = acrílico)."""
    import ctypes
    from ctypes import byref, c_int

    dwm = ctypes.windll.dwmapi
    dwm.DwmSetWindowAttribute(hwnd, 20, byref(c_int(1)), 4)  # DWMWA_USE_IMMERSIVE_DARK_MODE
    return dwm.DwmSetWindowAttribute(hwnd, 38, byref(c_int(kind)), 4) == 0  # DWMWA_SYSTEMBACKDROP_TYPE


def _blur_behind(hwnd, on):
    """Desfoque leve e clássico do DWM (DwmEnableBlurBehindWindow) na janela inteira."""
    import ctypes
    from ctypes import Structure, byref, c_int, c_void_p, c_uint

    class BlurBehind(Structure):
        _fields_ = [("flags", c_uint), ("enable", c_int), ("region", c_void_p), ("transition", c_int)]

    return ctypes.windll.dwmapi.DwmEnableBlurBehindWindow(c_void_p(hwnd), byref(BlurBehind(1, 1 if on else 0, None, 0))) == 0


def enable_system_blur(window, on, level="light"):
    """Transparência e desfoque do que está atrás da janela. `level`: 'none' (transparente, sem desfoque), 'light'
    (desfoque leve do DWM) ou 'strong' (acrílico, o mais fosco). Fora do Windows não faz nada. Devolve True se o sistema aceitou."""
    if not sys.platform.startswith("win"):
        return False
    try:
        hwnd = int(window.winId())
        _accent(hwnd, ACCENT_DISABLED, 0)  # parte sempre de uma janela sem efeito, para os níveis não se somarem
        _dwm_backdrop(hwnd, 1)
        _blur_behind(hwnd, False)
        extended = _extend_frame(hwnd)  # com ou sem desfoque, o alfa da janela só vale com o vidro estendido
        if not on:
            return extended
        if level == "none":  # transparente, sem desfoque: o mesmo mecanismo do acrílico, só sem o efeito
            return _accent(hwnd, ACCENT_TRANSPARENT, 0x00000000) or extended
        if level == "strong":
            # tom quase transparente (ABGR): quem escurece o vidro é o desenho do próprio tema
            if _accent(hwnd, ACCENT_ACRYLIC, 0x14181410):
                return True
            return _dwm_backdrop(hwnd, 3)
        return _blur_behind(hwnd, True) or extended
    except Exception:  # noqa: BLE001  versão do Windows sem suporte: segue só com a transparência do Qt
        return False
