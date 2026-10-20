"""Window sizing only; engineering simulation and sensor settings stay fixed."""

import ctypes
import os


def desktop_size():
    """Read the existing X11 desktop, falling back conservatively without a display."""
    try:
        x11 = ctypes.CDLL('libX11.so.6')
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XDisplayWidth.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x11.XDisplayHeight.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        display = x11.XOpenDisplay(None)
        if display:
            try:
                return x11.XDisplayWidth(display, 0), x11.XDisplayHeight(display, 0)
            finally:
                x11.XCloseDisplay(display)
    except (OSError, AttributeError):
        pass
    return 1920, 1080


def window_profile(presentation=False, desktop=None):
    """Keep the proven 1280x720 renderer; size only the presentation GUI."""
    if not presentation:
        return {'stonefish': (1280, 720), 'gui': (1280, 880)}
    width, height = desktop if desktop is not None else desktop_size()
    if desktop is None and os.environ.get('NEPTUNE_PRESENTATION_WIDTH'):
        size = (max(640, int(os.environ['NEPTUNE_PRESENTATION_WIDTH'])),
                max(540, int(os.environ['NEPTUNE_PRESENTATION_HEIGHT'])))
        return {'stonefish': (1280, 720), 'gui': size}
    # The cap also leaves room on a 2560px / 125%-scaled Windows desktop.
    size = (max(640, min(1000, (width-64)//2)), max(480, min(800, height-120)))
    return {'stonefish': (1280, 720), 'gui': size}
