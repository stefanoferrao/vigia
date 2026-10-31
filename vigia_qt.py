"""VigIA Qt shell — one interface for Linux and Windows.

Frameless, always-on-top pill with provider usage and optional CPU/RAM/GPU.
Everything platform-specific (paths, metrics, autostart) lives in vigia_core.
"""

import ctypes
import math
import os
import signal
import subprocess
import sys
import threading
import time

from PySide6.QtCore import (QAbstractAnimation, QByteArray, QCoreApplication, QEasingCurve,
                            QEvent, QObject, QPoint, QPointF, QPropertyAnimation, QRect, QRectF, QSize, Qt,
                            QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import (
    QAction, QActionGroup, QColor, QCursor, QFont, QFontMetrics, QGuiApplication,
    QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QApplication, QGraphicsOpacityEffect, QBoxLayout, QLabel,
                               QMenu, QSizePolicy, QSpacerItem, QWidget, QWidgetAction)

import vigia_core as core

SIZES = {
    "small": {"font": 9, "icon": 10, "pad_v": 3, "pad_h": 7,
              "gap": 5, "gap_block": 14, "gap_group": 24},
    "medium": {"font": 10, "icon": 12, "pad_v": 4, "pad_h": 9,
               "gap": 6, "gap_block": 16, "gap_group": 28},
    "large": {"font": 13, "icon": 15, "pad_v": 6, "pad_h": 12,
              "gap": 9, "gap_block": 20, "gap_group": 34},
}
SERVER_NAME = "vigia"
ISLAND_WIDTH = 120     # collapsed bar: a Dynamic-Island style handle at the top edge
ISLAND_HEIGHT = 8
ISLAND_COLLAPSE_MS = 400
ISLAND_EXPAND_MS = 470  # unfold: fast start, springy landing
ISLAND_HIDE_MS = 240    # fold back: content leaves first, then the pill closes
MAX_WIDGET_SIZE = 16777215
THEME_MS = 280          # colour cross-fade when the theme changes
FADE_MS = 220           # colour cross-fade when a reading changes state
GLIDE_MS = 420          # a number and its bar glide to a new reading
SHOW_MS = 180           # pills fade in/out when shown or hidden
MENU_MS = 300           # menus spring open
WAVE_MS = 900           # a colour change sends a ring out from the pill
HOVER_MS = 140          # border warms up to the accent under the cursor
PULSE_MS = 2000         # one breath of a critical reading
SHADOW_PAD = 12         # soft shadow around the pill: extent, and offset below
SHADOW_DROP = 3
def menu_qss():
    """Menu stylesheet built from the active theme."""
    t = core.THEME
    return f"""
QMenu {{
    background-color: {t['menu-surface']};
    color: {t['text-primary']};
    border: 1px solid {t['menu-border']};
    padding: 4px;
    border-radius: 8px;
}}
QMenu::item {{ padding: 5px 22px 5px 22px; border-radius: 5px; }}
QMenu::item:selected {{ background-color: {t['menu-hover']}; }}
QMenu::item:disabled {{ color: {t['text-disabled']}; }}
QMenu::separator {{ height: 1px; background: {t['menu-border']}; margin: 4px 6px; }}
QMenu::indicator {{ width: 12px; height: 12px; }}
"""


# ------------------------------------------------------------------------- helpers

def script_assets():
    here = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(here, "assets")


def loaded_svg(path, tint=None):
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError:
        return None
    if tint:
        data = data.replace(b"#ffffff", tint.encode()).replace(
            b'fill="#a8afba"', f'fill="{tint}"'.encode())
    return QByteArray(data)


def svg_pixmap(renderer, size, dpr=1.0):
    pixels = max(1, int(round(size * dpr)))
    pixmap = QPixmap(pixels, pixels)
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    return pixmap


def provider_pixmap(brand, tint, size, dpr):
    path = core.icon_path(brand)
    if not path:
        return None
    data = loaded_svg(path, tint)
    if data is None:
        return None
    renderer = QSvgRenderer(data)
    if not renderer.isValid():
        return None
    return svg_pixmap(renderer, size, dpr)


def gear_pixmap(size, dpr):
    data = loaded_svg(os.path.join(script_assets(), "gear.svg"))
    if data is None:
        return None
    renderer = QSvgRenderer(data)
    if not renderer.isValid():
        return None
    return svg_pixmap(renderer, size, dpr)


def pretty_accelerator(accelerator):
    """Human form of an accelerator: '<Control><Alt>u' -> 'Ctrl+Alt+U'."""
    names = {"control": "Ctrl", "ctrl": "Ctrl", "alt": "Alt", "mod1": "Alt",
             "shift": "Shift", "super": "Super", "meta": "Super", "win": "Super"}
    cleaned = str(accelerator or "").replace("<", "+").replace(">", "+")
    parts = []
    for part in cleaned.split("+"):
        part = part.strip()
        if not part:
            continue
        label = names.get(part.lower())
        if label is None:
            label = part.upper() if len(part) == 1 else part
        parts.append(label)
    return "+".join(parts) or "—"


def parse_accelerator(accelerator):
    """'<Control><Alt>u' or 'Control+Alt+u' -> ({"control","alt"}, "u")."""
    mods = set()
    buffer = ""
    inside = False
    state = {"key": ""}

    def flush(token):
        name = token.strip().lower()
        if not name:
            return
        if name in ("control", "ctrl"):
            mods.add("control")
        elif name in ("alt", "mod1"):
            mods.add("alt")
        elif name == "shift":
            mods.add("shift")
        elif name in ("super", "meta", "win"):
            mods.add("super")
        else:
            state["key"] = name

    for char in accelerator:
        if char == "<":
            inside = True
            buffer = ""
        elif char == ">":
            inside = False
            flush(buffer)
            buffer = ""
        elif char in "+ ":
            flush(buffer)
            buffer = ""
        else:
            buffer += char
    flush(buffer)
    return mods, state["key"]


# -------------------------------------------------------------------------- hotkey

class Hotkey(QObject):
    triggered = Signal()

    def __init__(self, accelerator):
        super().__init__()
        self.accelerator = accelerator
        self.active = False
        self.thread = None

    def start(self):
        mods, key = parse_accelerator(self.accelerator)
        if not key:
            core.log(f"hotkey ignored (unparsable): {self.accelerator}")
            return
        if core.IS_WINDOWS:
            self.thread = threading.Thread(target=self._windows_loop, args=(mods, key), daemon=True)
        elif os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
            core.log("hotkey unavailable on Wayland; bind `vigia --toggle` in the desktop settings")
            return
        else:
            self.thread = threading.Thread(target=self._x11_loop, args=(mods, key), daemon=True)
        self.thread.start()

    # -- Windows -------------------------------------------------------------
    def _windows_loop(self, mods, key):
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        MOD = {"alt": 0x0001, "control": 0x0002, "shift": 0x0004, "super": 0x0008}
        mask = 0
        for name in mods:
            mask |= MOD.get(name, 0)
        vk = ord(key.upper()) if len(key) == 1 else 0
        if key.startswith("f") and key[1:].isdigit():
            vk = 0x6F + int(key[1:])
        if not vk or not user32.RegisterHotKey(None, 1, mask, vk):
            core.log(f"hotkey refused by Windows: {self.accelerator}")
            return
        self.active = True
        core.log(f"hotkey bound: {self.accelerator}")
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            if message.message == 0x0312:  # WM_HOTKEY
                self.triggered.emit()
        user32.UnregisterHotKey(None, 1)

    # -- X11 -----------------------------------------------------------------
    def _x11_loop(self, mods, key):
        try:
            xlib = ctypes.cdll.LoadLibrary("libX11.so.6")
        except OSError:
            core.log("hotkey unavailable: libX11 not found")
            return
        xlib.XOpenDisplay.restype = ctypes.c_void_p
        xlib.XDefaultRootWindow.restype = ctypes.c_ulong
        xlib.XStringToKeysym.restype = ctypes.c_ulong
        display = xlib.XOpenDisplay(None)
        if not display:
            core.log("hotkey unavailable: cannot open X display")
            return
        root = xlib.XDefaultRootWindow(ctypes.c_void_p(display))
        keysym = xlib.XStringToKeysym(key.encode())
        keycode = xlib.XKeysymToKeycode(ctypes.c_void_p(display), ctypes.c_ulong(keysym))
        mask = 0
        if "shift" in mods:
            mask |= 1 << 0
        if "control" in mods:
            mask |= 1 << 2
        if "alt" in mods:
            mask |= 1 << 3
        if "super" in mods:
            mask |= 1 << 6
        variants = (0, 1 << 1, 1 << 4, (1 << 1) | (1 << 4))  # num/caps lock
        for extra in variants:
            xlib.XGrabKey(ctypes.c_void_p(display), keycode, ctypes.c_uint(mask | extra),
                          ctypes.c_ulong(root), True, 1, 1)
        xlib.XSync(ctypes.c_void_p(display), False)
        self.active = True
        core.log(f"hotkey bound: {self.accelerator}")
        event = (ctypes.c_char * 192)()
        while True:
            xlib.XNextEvent(ctypes.c_void_p(display), event)
            event_type = ctypes.cast(event, ctypes.POINTER(ctypes.c_int))[0]
            if event_type == 2:  # KeyPress
                self.triggered.emit()


# ----------------------------------------------------------------------------- pill

class AccentPicker(QWidget):
    """Colour picker that lives inside the menu: saturation/value square, hue bar, swatches.

    Dragging previews the colour on the pills; releasing (or a swatch) commits it, so the
    menu never closes and the pill stays open behind it."""
    previewed = Signal(str)
    committed = Signal(str)
    SWATCHES = ("#8b93ff", "#4cc38a", "#f2bd34", "#ff6b68", "#d97757", "#4285f4",
                "#c084fc", "#e6e6ec")
    PAD, BOX_W, BOX_H, BAR_H, DOT = 10, 200, 110, 12, 18

    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.hue, self.sat, self.val, _ = QColor(color).getHsvF()
        self.hue = max(0.0, self.hue)  # greys report hue -1
        self.drag = None              # "box" | "bar" while the mouse is down
        self.grab = 0.0               # handles swell while held; eased toward grab_goal
        self.grab_goal = 0.0
        self.swell = [0.0] * len(self.SWATCHES)  # swatches grow under the cursor
        self.swell_goal = [0.0] * len(self.SWATCHES)
        self.ease = QTimer(self)
        self.ease.setInterval(16)
        self.ease.timeout.connect(self.settle)
        self.setFixedSize(self.BOX_W + 2 * self.PAD, 2 * self.PAD + self.BOX_H + 8
                          + self.BAR_H + 10 + self.DOT + 8 + 14)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)

    def settle(self):
        """Ease every swelling value toward its goal; stop the timer once all have landed."""
        moving = False
        self.grab += (self.grab_goal - self.grab) * 0.32
        if abs(self.grab_goal - self.grab) > 0.004:
            moving = True
        else:
            self.grab = self.grab_goal
        for index, goal in enumerate(self.swell_goal):
            self.swell[index] += (goal - self.swell[index]) * 0.30
            if abs(goal - self.swell[index]) > 0.004:
                moving = True
            else:
                self.swell[index] = goal
        self.update()
        if not moving:
            self.ease.stop()

    def aim(self):
        if not self.ease.isActive():
            self.ease.start()

    # -- geometry ------------------------------------------------------------
    def box_rect(self):
        return QRect(self.PAD, self.PAD, self.BOX_W, self.BOX_H)

    def bar_rect(self):
        return QRect(self.PAD, self.PAD + self.BOX_H + 8, self.BOX_W, self.BAR_H)

    def swatch_rect(self, index):
        step = (self.BOX_W - self.DOT) / (len(self.SWATCHES) - 1)
        y = self.bar_rect().bottom() + 10
        return QRect(int(self.PAD + index * step), y, self.DOT, self.DOT)

    def color(self):
        return QColor.fromHsvF(self.hue, self.sat, self.val)

    def set_color(self, color):
        """Follow a colour changed from outside (e.g. the reset entry)."""
        self.hue, self.sat, self.val, _ = QColor(color).getHsvF()
        self.hue = max(0.0, self.hue)
        self.update()

    # -- paint ---------------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        border = QColor(core.THEME["menu-border"])
        text = QColor(core.THEME["text-secondary"])

        box = self.box_rect()
        clip = QPainterPath()
        clip.addRoundedRect(box, 6, 6)
        painter.save()
        painter.setClipPath(clip)
        painter.fillRect(box, QColor.fromHsvF(self.hue, 1.0, 1.0))
        across = QLinearGradient(box.left(), 0, box.right(), 0)
        across.setColorAt(0, QColor(255, 255, 255))
        across.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(box, across)
        down = QLinearGradient(0, box.top(), 0, box.bottom())
        down.setColorAt(0, QColor(0, 0, 0, 0))
        down.setColorAt(1, QColor(0, 0, 0))
        painter.fillRect(box, down)
        painter.restore()
        painter.setPen(QPen(border, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(box, 6, 6)
        self.handle(painter, box.left() + self.sat * box.width(),
                    box.top() + (1 - self.val) * box.height(), self.color(),
                    6 + 5 * self.grab if self.drag == "box" or self.grab_goal == 0 else 6)

        bar = self.bar_rect()
        rainbow = QLinearGradient(bar.left(), 0, bar.right(), 0)
        for step in range(7):
            rainbow.setColorAt(step / 6, QColor.fromHsvF(step / 6 if step < 6 else 0.0, 1, 1))
        painter.setPen(Qt.NoPen)
        painter.setBrush(rainbow)
        painter.drawRoundedRect(bar, bar.height() / 2, bar.height() / 2)
        self.handle(painter, bar.left() + self.hue * bar.width(), bar.center().y() + 0.5,
                    QColor.fromHsvF(self.hue, 1, 1),
                    6 + 4 * self.grab if self.drag == "bar" or self.grab_goal == 0 else 6)

        for index, hex_color in enumerate(self.SWATCHES):
            rect = self.swatch_rect(index)
            swell = self.swell[index]
            grown = rect.adjusted(1, 1, -1, -1)
            grown = QRectF(grown).adjusted(-3.5 * swell, -3.5 * swell, 3.5 * swell, 3.5 * swell)
            painter.setPen(QPen(border, 1))
            painter.setBrush(QColor(hex_color))
            painter.drawEllipse(grown)
            if QColor(hex_color).name() == self.color().name():
                painter.setPen(QPen(QColor(core.THEME["text-primary"]), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(grown.adjusted(-2, -2, 2, 2))

        painter.setPen(text)
        font = QFont(self.font())
        font.setPixelSize(11)
        painter.setFont(font)
        painter.drawText(QRect(self.PAD, self.height() - 22, self.BOX_W, 14),
                         Qt.AlignLeft | Qt.AlignVCenter, self.color().name().upper())
        painter.end()

    def handle(self, painter, x, y, fill, radius=6):
        painter.setBrush(fill)
        painter.setPen(QPen(QColor(0, 0, 0, 120), 3))
        painter.drawEllipse(QPointF(x, y), radius, radius)
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawEllipse(QPointF(x, y), radius, radius)

    # -- input ---------------------------------------------------------------
    def mousePressEvent(self, event):
        point = event.position().toPoint()
        for index, hex_color in enumerate(self.SWATCHES):
            if self.swatch_rect(index).contains(point):
                self.hue, self.sat, self.val, _ = QColor(hex_color).getHsvF()
                self.hue = max(0.0, self.hue)
                self.swell[index] = 2.0  # a swatch pops past its hover size, then settles
                self.aim()
                self.committed.emit(self.color().name())
                return
        if self.bar_rect().adjusted(0, -6, 0, 6).contains(point):
            self.drag = "bar"
        elif self.box_rect().contains(point):
            self.drag = "box"
        else:
            return
        self.grab_goal = 1.0
        self.aim()
        self.track(point)

    def mouseMoveEvent(self, event):
        point = event.position().toPoint()
        if self.drag:
            self.track(point)
            return
        for index in range(len(self.SWATCHES)):
            self.swell_goal[index] = 1.0 if self.swatch_rect(index).adjusted(-3, -3, 3, 3).contains(point) else 0.0
        self.aim()

    def leaveEvent(self, event):
        self.swell_goal = [0.0] * len(self.SWATCHES)
        self.aim()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drag:
            self.track(event.position().toPoint())
            self.drag = None
            self.grab_goal = 0.0
            self.aim()
            self.committed.emit(self.color().name())

    def track(self, point):
        if self.drag == "box":
            box = self.box_rect()
            self.sat = min(1.0, max(0.0, (point.x() - box.left()) / box.width()))
            self.val = 1.0 - min(1.0, max(0.0, (point.y() - box.top()) / box.height()))
        else:
            bar = self.bar_rect()
            self.hue = min(0.999, max(0.0, (point.x() - bar.left()) / bar.width()))
        self.update()
        self.previewed.emit(self.color().name())


class StickyMenu(QMenu):
    """Keeps the popup open after a setting changes.

    The root menu and its submenus all stay open, so several settings can be
    changed in a row; only actions flagged with "closes_menu" close the popup.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A translucent, frameless popup lets the stylesheet round the corners.
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint
                            | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def showEvent(self, event):
        """Spring open: grows from where it was called (a submenu from its parent's edge),
        overshoots a touch, and slides into place while fading in."""
        super().showEvent(event)
        final = QRect(self.geometry())
        if final.width() < 20 or final.height() < 20:
            return
        submenu = isinstance(self.parentWidget(), QMenu)
        curve = QEasingCurve(QEasingCurve.OutBack)
        curve.setOvershoot(1.9)

        def step(raw):
            t = curve.valueForProgress(raw)
            scale = 0.80 + 0.20 * t
            width, height = round(final.width() * scale), round(final.height() * scale)
            if submenu:  # hinges on its left edge, slides out sideways
                x = final.x() - round((1.0 - min(t, 1.0)) * 16)
                y = final.y()
            else:        # hinges on the top centre, drops down a little
                x = final.x() + (final.width() - width) // 2
                y = final.y() - round((1.0 - min(t, 1.0)) * 12)
            self.setGeometry(x, y, width, height)
            self.setWindowOpacity(max(0.0, min(1.0, raw * 2.4)))

        def done():
            self.setGeometry(final)
            self.setWindowOpacity(1.0)

        anim = QVariantAnimation(self)
        anim.setDuration(MENU_MS)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.valueChanged.connect(step)
        anim.finished.connect(done)
        self.fade_in = anim
        step(0.0)
        anim.start()

    def _activate(self, action):
        if action is None or not action.isEnabled() or action.menu() is not None:
            return False
        action.trigger()
        if action.property("closes_menu"):
            self.close_chain()
        return True

    def close_chain(self):
        """Hide this menu and every menu it hangs from (submenu -> root)."""
        menu = self
        while isinstance(menu, QMenu):
            menu.hide()
            menu = menu.parentWidget()

    def mouseReleaseEvent(self, event):
        if self._activate(self.actionAt(event.position().toPoint())):
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            if self._activate(self.activeAction()):
                event.accept()
                return
        super().keyPressEvent(event)


class GearLabel(QLabel):
    """Clickable gear that keeps the press so the release lands here."""

    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.pressed = False
        self.angle = 0.0   # degrees, driven by the pill's hover progress
        self.squash = 1.0  # < 1 while the button is held down

    def paintEvent(self, event):
        pixmap = self.pixmap()
        if pixmap is None or pixmap.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self.angle)
        painter.scale(self.squash, self.squash)
        half_w, half_h = self.width() / 2, self.height() / 2
        painter.drawPixmap(QRectF(-half_w, -half_h, self.width(), self.height()),
                           pixmap, QRectF(pixmap.rect()))
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.pressed = True
            self.squash = 0.78
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            pressed, self.pressed = self.pressed, False
            self.squash = 1.0
            self.update()
            if pressed:
                self.callback()
            event.accept()
            return
        super().mouseReleaseEvent(event)


def mix(a, b, t):
    """Linear blend of two QColors, t = 0 -> a, t = 1 -> b."""
    return QColor(*(round(x + (y - x) * t) for x, y in (
        (a.red(), b.red()), (a.green(), b.green()),
        (a.blue(), b.blue()), (a.alpha(), b.alpha()))))


def drop(widget):
    """deleteLater() that tolerates a widget Qt already tore down (app shutdown)."""
    try:
        widget.deleteLater()
    except RuntimeError:
        pass


class Reading(QWidget):
    """A number with a thin usage bar underneath.

    A change of state cross-fades the colours instead of snapping, and a critical
    value breathes with the pill's shared pulse.
    """
    BAR = 2

    def __init__(self, pill, key, text, percent, colors):
        super().__init__()
        self.pill = pill
        self.key = key
        self.text = text
        self.percent = percent
        self.anim = None
        self.glide_anim = None
        self.tweens = {}
        self.reveal = 1.0   # 0 -> 1: slides up and fades in when the pill opens
        self.hot = 0.0      # cursor over this reading
        self.flash = 0.0    # the value just changed
        self.shake = 0.0    # just turned critical
        self.is_hot = False
        self.shown = pill.shown_memory.get(key, percent)  # what is on screen right now
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        font = QFont(self.font())
        font.setPixelSize(pill.css["font"])
        font.setBold(True)
        if hasattr(font, "setFeature"):
            font.setFeature(QFont.Tag("tnum"), 1)  # steady digit width: numbers don't jitter
        self.setFont(font)
        metrics = QFontMetrics(font)
        self.bars = bool(pill.app.config.get("bars"))
        self.text_height = metrics.height()
        # Fixed "100%" slot: the icon -> number gap stays constant whatever the number is.
        self.setFixedWidth(metrics.horizontalAdvance("100%") + 2)
        self.setFixedHeight(max(self.text_height, metrics.ascent() + 2 + self.BAR + 1)
                            if self.bars else self.text_height)

        tint, bar, self.critical = colors
        self.tint, self.bar = (QColor(c) for c in pill.tint_memory.get(key, (tint, bar)))
        self.target = (QColor(self.tint), QColor(self.bar))
        self.retarget(colors)
        self.glide()
        was_critical = pill.crit_memory.get(key, self.critical)
        pill.crit_memory[key] = self.critical
        if self.critical and not was_critical:
            self.tween("shake", 0.0, 1.0, 520, QEasingCurve.Linear)

    def tween(self, attr, start, end, ms, curve=QEasingCurve.OutCubic, delay=0, overshoot=None):
        """Drive self.<attr> from start to end; a newer tween on the same attr replaces it."""
        old = self.tweens.pop(attr, None)
        if old is not None:
            old.stop()
        anim = QVariantAnimation(self)
        anim.setDuration(ms)
        easing = QEasingCurve(curve)
        if overshoot is not None:
            easing.setOvershoot(overshoot)
        anim.setEasingCurve(easing)
        anim.setStartValue(float(start))
        anim.setEndValue(float(end))
        anim.valueChanged.connect(lambda value: (setattr(self, attr, float(value)), self.update()))
        self.tweens[attr] = anim
        setattr(self, attr, float(start))
        if delay:
            QTimer.singleShot(delay, lambda: self.begin(anim))
        else:
            anim.start()

    @staticmethod
    def begin(anim):
        try:
            anim.start()
        except RuntimeError:  # the reading was rebuilt away before its turn came
            pass

    def enter(self, delay):
        self.tween("reveal", 0.0, 1.0, 460, QEasingCurve.OutBack, delay, overshoot=2.2)

    def set_hot(self, hot):
        if hot != self.is_hot:
            self.is_hot = hot
            self.tween("hot", self.hot, 1.0 if hot else 0.0, 170)

    def set_reading(self, text, percent, colors):
        was_critical = self.critical
        self.text = text
        self.percent = percent
        self.retarget(colors)
        self.pill.crit_memory[self.key] = self.critical
        if self.critical and not was_critical:
            self.tween("shake", 0.0, 1.0, 520, QEasingCurve.Linear)
        self.glide()
        self.update()

    def gliding(self):
        return (isinstance(self.percent, (int, float)) and isinstance(self.shown, (int, float))
                and self.text.endswith("%"))

    def glide(self):
        """Slide the bar and count the number toward the new reading instead of jumping."""
        if self.glide_anim is not None:
            self.glide_anim.stop()
            self.glide_anim = None
        if not self.gliding() or abs(self.percent - self.shown) < 0.5:
            self.shown = self.percent
            self.pill.shown_memory[self.key] = self.percent
            return
        start = self.shown
        if self.key.startswith("provider:") and abs(self.percent - self.shown) >= 1:
            # only a provider's quota is worth a halo; CPU/RAM/GPU change on every tick
            self.tween("flash", 1.0, 0.0, 950, QEasingCurve.OutQuad)
        anim = QVariantAnimation(self)
        anim.setDuration(GLIDE_MS)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.valueChanged.connect(lambda t: self.glide_to(start, t))
        anim.finished.connect(lambda: self.glide_to(start, 1.0))
        self.glide_anim = anim
        anim.start()

    def glide_to(self, start, t):
        self.shown = start + (self.percent - start) * float(t)
        self.pill.shown_memory[self.key] = self.shown
        self.update()

    def retarget(self, colors):
        tint, bar, self.critical = colors
        tint, bar = QColor(tint), QColor(bar)
        self.pill.tint_memory[self.key] = (tint, bar)
        if (tint, bar) == self.target:
            return
        self.target = (tint, bar)
        if self.anim is not None:
            self.anim.stop()
        start = (QColor(self.tint), QColor(self.bar))
        anim = QVariantAnimation(self)
        anim.setDuration(FADE_MS)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.valueChanged.connect(lambda t: self.fade(start, t))
        self.anim = anim
        anim.start()

    def follow_theme(self, colors):
        """Jump to the colours of the theme being cross-faded (the pill drives the fade)."""
        tint, bar, self.critical = colors
        self.tint, self.bar = QColor(tint), QColor(bar)
        self.target = (QColor(self.tint), QColor(self.bar))
        self.pill.tint_memory[self.key] = self.target
        if self.anim is not None:
            self.anim.stop()
        self.update()

    def fade(self, start, t):
        self.tint = mix(start[0], self.target[0], t)
        self.bar = mix(start[1], self.target[1], t)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        width = self.width() - 2
        value = self.shown if self.gliding() else self.percent
        label = f"{round(value)}%" if self.gliding() else self.text
        glow = max(self.hot * 0.20, self.flash * 0.34)
        if glow > 0.01:  # soft halo behind the number: hover, or a fresh change
            halo = QColor(self.bar)
            halo.setAlpha(int(255 * glow))
            painter.setPen(Qt.NoPen)
            painter.setBrush(halo)
            painter.drawRoundedRect(QRectF(-3, -2, self.width() + 6, self.height() + 4), 6, 6)
        if self.shake > 0:
            painter.translate(math.sin(self.shake * math.pi * 7) * (1 - self.shake) * 3.2, 0)
        painter.translate(0, (1.0 - self.reveal) * 9)
        painter.setOpacity(max(0.0, min(1.0, self.reveal)))
        if self.bars and isinstance(value, (int, float)):
            y = self.height() - self.BAR
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(core.THEME["divider"]))
            painter.drawRoundedRect(0, y, width, self.BAR, 1, 1)
            fill = round(width * max(0.0, min(100.0, value)) / 100)
            if fill > 0:
                painter.setOpacity(self.pulse_opacity())
                painter.setBrush(self.bar)
                painter.drawRoundedRect(0, y, max(fill, self.BAR), self.BAR, 1, 1)
        painter.setOpacity(self.pulse_opacity())
        painter.setFont(self.font())
        painter.setPen(mix(self.tint, QColor(core.THEME["text-primary"]), self.hot * 0.55))
        painter.drawText(QRect(0, 0, self.width(), self.text_height),
                         Qt.AlignLeft | Qt.AlignVCenter, label)
        painter.end()

    def pulse_opacity(self):
        entrance = max(0.0, min(1.0, self.reveal))
        if self.critical and self.pill.pulse_running():
            return entrance * (1.0 - 0.35 * self.pill.pulse_value)
        return entrance


class Shadow(QWidget):
    """Click-through window behind a pill that paints its soft drop shadow."""

    def __init__(self, pill):
        flags = (Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
                 | Qt.WindowTransparentForInput)
        if pill.app.config.get("always_on_top"):
            flags |= Qt.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.pill = pill
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def follow(self):
        area = self.pill.screen.geometry()
        self.setGeometry(self.pill.geometry().adjusted(
            -SHADOW_PAD, -SHADOW_PAD, SHADOW_PAD, SHADOW_PAD).intersected(area))

    def paintEvent(self, event):
        inner = self.pill.geometry().translated(-self.x(), -self.y()).adjusted(0, 0, -1, -1)
        dark = QColor(core.THEME["surface"]).lightness() < 128
        color = QColor(0, 0, 0, 7 if dark else 5)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        base = inner.translated(0, SHADOW_DROP)
        for grow in range(SHADOW_PAD - SHADOW_DROP, 0, -1):
            ring = base.adjusted(-grow, -grow, grow, grow)
            path = QPainterPath()
            radius = min(ring.width(), ring.height()) / 2
            path.addRoundedRect(ring, radius, radius)
            painter.fillPath(path, color)
        # Keep the pill itself clean: a translucent pill must not darken from below.
        painter.setCompositionMode(QPainter.CompositionMode_Clear)
        cut = QPainterPath()
        radius = min(inner.width(), inner.height()) / 2
        cut.addRoundedRect(inner, radius, radius)
        painter.fillPath(cut, Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        wave = self.pill.wave_t
        if 0.0 < wave < 1.0:  # shock rings in the accent colour, three trailing each other
            for lag in (0.0, 0.14, 0.28):
                t = max(0.0, min(1.0, (wave - lag) / (1.0 - 0.28)))
                if t <= 0.0:
                    continue
                grow = 1 + t * (SHADOW_PAD - 3)
                ring = inner.adjusted(-grow, -grow, grow, grow)
                accent = QColor(core.THEME["primary"])
                accent.setAlpha(int(210 * (1.0 - t) ** 1.6))
                painter.setPen(QPen(accent, 2.0 - t))
                painter.setBrush(Qt.NoBrush)
                radius = min(ring.width(), ring.height()) / 2
                painter.drawRoundedRect(ring, radius, radius)
        painter.end()


class Pill(QWidget):
    def __init__(self, app, screen_index):
        flags = Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
        if app.config.get("always_on_top"):
            flags |= Qt.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.app = app
        self.screen_index = screen_index
        self.screen = app.screens()[screen_index]
        self.hovered = False
        self.drag_offset = None
        self.drag_origin = QPoint(0, 0)
        self.drag_started = False
        self.readings = []
        self.themed = []          # restyle callables for widgets that carry theme colours
        self.system_labels = {}
        self.crit_memory = {}     # was each reading critical last time, so a rebuild can still shake
        self.shown_memory = {}    # last displayed value per reading key, for glides across rebuilds
        self.vis_anim = None
        self.snap_anim = None
        self.wave_t = 1.0         # 0 -> 1 while a colour-change ring travels outward
        self.wave_anim = None
        self.tint_memory = {}     # last colours per reading key, for cross-fades across rebuilds
        self.pulse_value = 0.0
        self.pulse_anim = None
        self.hover_t = 0.0
        self.hover_anim = None
        self.rows = []
        self.island_open = False
        self.shadow = Shadow(self)
        self.destroyed.connect(lambda *_, shadow=self.shadow: drop(shadow))

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowTitle(core.APP_NAME)
        self.setCursor(Qt.SizeAllCursor)
        self.setMouseTracking(True)

        self.css = SIZES[app.config.get("size")]
        # The content lives on its own fixed-size widget: resizing the window while
        # the island unfolds then clips it instead of reflowing the labels.
        self.content = QWidget(self)
        self.box = QBoxLayout(QBoxLayout.LeftToRight, self.content)
        self.box.setContentsMargins(self.css["pad_h"], self.css["pad_v"],
                                    max(2, self.css["pad_h"] - 2), self.css["pad_v"])
        self.box.setSpacing(self.css["gap"])
        self.island_anim = None
        self.content_effect = QGraphicsOpacityEffect(self.content)
        self.content_effect.setOpacity(1.0)
        self.content_effect.setEnabled(False)
        self.content.setGraphicsEffect(self.content_effect)
        self.build()
        self.hover_timer = QTimer(self)
        self.hover_timer.timeout.connect(self.poll_hover)
        self.hover_timer.start(60)
        self.collapse_timer = QTimer(self)
        self.collapse_timer.setSingleShot(True)
        self.collapse_timer.timeout.connect(self.maybe_collapse)
        self.place()

    # -- build ---------------------------------------------------------------
    def clear(self):
        while self.box.count():
            item = self.box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()  # gone this frame, not at the next event-loop turn
                widget.deleteLater()
        self.readings = []
        self.themed = []
        self.system_labels = {}

    def restyle(self):
        """Repaint with core.THEME as it is right now (called every frame of a theme fade)."""
        for apply in self.themed:
            apply()
        for reading in self.readings:
            reading.follow_theme(self.reading_colors(reading.percent))
        self.update()
        self.shadow.update()

    def reading_colors(self, percent):
        config = self.app.config
        style = config.get("icon_style")
        warn, critical = config.get("alert_warn"), config.get("alert_critical")
        return (core.value_tint(style, percent, warn, critical),
                core.bar_tint(style, percent, warn, critical),
                core.is_critical(style, percent, critical))

    def reading(self, key, text, percent):
        widget = Reading(self, key, text, percent, self.reading_colors(percent))
        self.readings.append(widget)
        return widget

    def muted_label(self, text):
        label = QLabel(text)
        font = QFont(label.font())
        font.setPixelSize(self.css["font"])
        label.setFont(font)
        self.themed.append(lambda: label.setStyleSheet(f"color: {core.THEME['text-secondary']};"))
        self.themed[-1]()
        label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        return label

    def divider(self):
        line = QWidget()
        length = max(6, self.css["icon"] - 2)
        line.setFixedSize(*((length, 1) if self.side_docked() else (1, length)))
        self.themed.append(lambda: line.setStyleSheet(f"background: {core.THEME['divider']};"))
        self.themed[-1]()
        line.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        return line

    # -- rhythm --------------------------------------------------------------
    def side_docked(self):
        """Docked to a left/right edge: the pill stacks its items top to bottom."""
        return self.island_on() and core.island_edge(self.island_anchor()) in ("left", "right")

    def orient_box(self):
        pad_h, pad_v = self.css["pad_h"], self.css["pad_v"]
        if self.side_docked():
            self.box.setDirection(QBoxLayout.TopToBottom)
            self.box.setContentsMargins(pad_v, pad_h, pad_v, max(2, pad_h - 2))
        else:
            self.box.setDirection(QBoxLayout.LeftToRight)
            self.box.setContentsMargins(pad_h, pad_v, max(2, pad_h - 2), pad_v)

    def add_item(self, widget):
        self.box.addWidget(widget, 0, Qt.AlignHCenter if self.side_docked() else Qt.Alignment())

    def add_gap(self, width):
        if width > 0:
            if self.side_docked():
                self.box.addSpacerItem(QSpacerItem(0, int(width), QSizePolicy.Minimum,
                                                   QSizePolicy.Fixed))
            else:
                self.box.addSpacerItem(QSpacerItem(int(width), 0, QSizePolicy.Fixed,
                                                   QSizePolicy.Minimum))

    def block_gap(self):
        """Extra space between two items (one provider, or one system reading)."""
        return max(0, self.css["gap_block"] - self.css["gap"])

    def group_gap(self):
        """Half of the AI <-> system gap; the divider sits in the middle."""
        return max(2, self.css["gap_group"] // 2 - self.css["gap"])

    def build(self):
        self.clear()
        self.orient_box()
        style = self.app.config.get("icon_style")
        dpr = self.devicePixelRatioF()

        hidden_providers = self.app.hidden_items("hide_providers")
        rows = [row for row in self.rows
                if row["id"].lower() not in hidden_providers][: self.app.config.get("max_providers")]
        if not rows:
            self.add_item(self.muted_label("—"))
        for index, row in enumerate(rows):
            if index:
                self.add_gap(self.block_gap())
            if not row["brand"] or not core.icon_path(row["brand"]):
                initials = QLabel(row["name"][:2].upper())
                font = QFont(initials.font())
                font.setPixelSize(self.css["font"])
                font.setBold(True)
                initials.setFont(font)
                self.themed.append(lambda w=initials: w.setStyleSheet(
                    f"color: {core.THEME['text-secondary']};"))
                self.themed[-1]()
                initials.setFixedWidth(self.css["icon"] + 2)
                initials.setAlignment(Qt.AlignCenter)
                initials.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                self.add_item(initials)
            else:
                icon = QLabel()
                self.themed.append(lambda w=icon, b=row["brand"]: w.setPixmap(provider_pixmap(
                    b, core.icon_tint(b, self.app.config.get("icon_style")),
                    self.css["icon"], dpr)))
                self.themed[-1]()
                icon.setFixedSize(self.css["icon"], self.css["icon"])
                icon.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                self.add_item(icon)
            value = self.reading(f"provider:{row['id']}", row["value"], row["percent"])
            value.setToolTip(f"{row['name']} — {row['label']}" if row["label"] else row["name"])
            self.add_item(value)

        if self.app.config.get("show_system"):
            hidden_system = self.app.hidden_items("hide_system")
            self.add_gap(self.group_gap())
            self.add_item(self.divider())
            self.add_gap(self.group_gap())
            counted = 0
            for name, reading in self.app.metrics.snapshot():
                if reading is None or name.lower() in hidden_system:
                    continue
                if counted:
                    self.add_gap(self.block_gap())
                counted += 1
                self.add_item(self.muted_label(name))
                value = self.reading(f"system:{name}", f"{reading}%", reading)
                self.add_item(value)
                self.system_labels[name] = value

        self.add_gap(self.block_gap())
        self.gear = GearLabel(self.show_menu)
        self.gear.setPixmap(gear_pixmap(max(9, self.css["icon"] - 2), dpr))
        self.gear.setFixedSize(max(9, self.css["icon"] - 2), max(9, self.css["icon"] - 2))
        self.gear.setCursor(Qt.PointingHandCursor)
        self.gear.setToolTip(self.app.config.t("gear"))
        self.gear_effect = QGraphicsOpacityEffect(self.gear)
        self.gear.setGraphicsEffect(self.gear_effect)
        self.sync_gear()
        self.add_item(self.gear)
        self.apply_island_state()

    # -- paint ---------------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(0, 0, -1, -1)
        radius = min(rect.width(), rect.height()) / 2
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        alpha = self.app.effective_alpha(self.hovered)
        fill = QColor(core.THEME["surface"])
        fill.setAlpha(int(alpha * 255))
        painter.fillPath(path, fill)
        if fill.lightness() < 128 and min(rect.width(), rect.height()) > ISLAND_HEIGHT + 2:
            # 1 px inner highlight along the top: a hint of depth on dark surfaces
            painter.setClipPath(path)
            painter.setPen(QPen(QColor(255, 255, 255, 18), 1))
            painter.drawLine(int(radius), 1, int(rect.width() - radius), 1)
            painter.setClipping(False)
        border = QColor(core.THEME["surface-border"])
        glow = max(self.hover_t, (1.0 - self.wave_t) ** 2 if self.wave_t < 1.0 else 0.0)
        if glow > 0:
            accent = QColor(core.THEME["primary"])
            accent.setAlpha(190)
            border = mix(border, accent, min(1.0, glow))
        painter.setPen(QPen(border, 1))
        painter.drawPath(path)
        painter.end()

    # -- island --------------------------------------------------------------
    def island_on(self):
        return bool(self.app.config.get("island"))

    def island_anchor(self):
        return self.app.config.get("island_anchor")

    def collapsed_size(self):
        """The resting handle: wide on a top/bottom edge, tall on a side edge."""
        if core.island_edge(self.island_anchor()) in ("left", "right"):
            return QSize(ISLAND_HEIGHT, ISLAND_WIDTH)
        return QSize(ISLAND_WIDTH, ISLAND_HEIGHT)

    def docked_rect(self, size, offset=None):
        area = self.screen.availableGeometry()
        x, y = core.island_position(
            (area.x(), area.y(), area.width(), area.height()), self.island_anchor(),
            size.width(), size.height(),
            self.app.island_offset(self) if offset is None else offset)
        return QRect(x, y, size.width(), size.height())

    def collapse_rect(self):
        return self.docked_rect(self.collapsed_size())

    def expanded_rect(self, size=None):
        return self.docked_rect(size or self.natural_size())

    def is_collapsed_size(self):
        return self.size() == self.collapsed_size()

    def natural_size(self):
        """Size the content wants; the layout runs on the container's own size."""
        self.box.activate()
        return self.box.sizeHint()

    def fit_content(self):
        """Pin the container to its natural size so the window can clip it."""
        size = self.natural_size()
        if self.content.size() != size:
            self.content.setFixedSize(size)
        self.center_content()
        return size

    def center_content(self):
        self.content.move((self.width() - self.content.width()) // 2,
                          (self.height() - self.content.height()) // 2)

    def show_children(self, visible):
        for index in range(self.box.count()):
            widget = self.box.itemAt(index).widget()
            if widget is not None:
                widget.setVisible(visible)

    def apply_island_state(self):
        """Collapsed: a small bar with the content hidden. Open: the whole pill."""
        opened = self.island_open or not self.island_on()
        self.show_children(opened)
        if self.island_busy() and self.island_open:
            self.fit_content()  # a rebuild landed mid-animation; let it finish
            return
        if opened:
            size = self.fit_content()
            self.setMinimumSize(0, 0)
            self.setMaximumSize(MAX_WIDGET_SIZE, MAX_WIDGET_SIZE)
            if self.size() != size:
                self.resize(size)
            self.center_content()
        else:
            self.setFixedSize(self.collapsed_size())
            self.center_content()
        self.setWindowOpacity(1.0)
        self.set_content_opacity(1.0)

    def island_busy(self):
        return (self.island_anim is not None
                and self.island_anim.state() == QAbstractAnimation.Running)

    def set_content_opacity(self, value):
        value = max(0.0, min(1.0, value))
        self.content_effect.setEnabled(value < 1.0)
        self.content_effect.setOpacity(value)

    def animate_island(self, opened):
        """Morph between the 8 px bar and the whole pill instead of snapping.

        One progress value drives both the outline and the content: on unfold the
        pill opens first and the content fades in over its second half; on fold
        the content fades out first and the pill closes behind it.
        """
        if self.island_anim is not None:
            self.island_anim.stop()
            self.island_anim = None
        start = self.geometry()
        if opened:
            self.cascade()
            self.show_children(True)
            self.fit_content()
            self.setMinimumSize(0, 0)
            self.setMaximumSize(MAX_WIDGET_SIZE, MAX_WIDGET_SIZE)
            end = self.expanded_rect()
            duration = ISLAND_EXPAND_MS
            curve = QEasingCurve(QEasingCurve.OutBack)  # springs a little past its size
            curve.setOvershoot(1.25)
        else:
            end = self.collapse_rect()
            duration = ISLAND_HIDE_MS
            curve = QEasingCurve(QEasingCurve.InOutCubic)
        if start == end:
            self.finish_island_anim()
            return
        # Interrupting a running fold/unfold: continue from the current opacity.
        base = (self.content_effect.opacity() if self.content_effect.isEnabled()
                else (0.0 if opened and min(start.width(), start.height()) <= ISLAND_HEIGHT else 1.0))

        def lerp(a, b, t):
            return round(a + (b - a) * t)

        def step(raw):
            eased = curve.valueForProgress(raw)
            self.setGeometry(QRect(lerp(start.x(), end.x(), eased),
                                   lerp(start.y(), end.y(), eased),
                                   lerp(start.width(), end.width(), eased),
                                   lerp(start.height(), end.height(), eased)))
            self.center_content()
            if opened:
                fade = (raw - 0.30) / 0.70
                fade = max(0.0, min(1.0, fade))
                self.set_content_opacity(max(base, fade * fade * (3 - 2 * fade)))
            else:
                fade = 1.0 - min(1.0, raw / 0.55)
                self.set_content_opacity(min(base, fade * fade * (3 - 2 * fade)))

        anim = QVariantAnimation(self)
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.valueChanged.connect(step)
        anim.finished.connect(self.finish_island_anim)
        self.island_anim = anim
        self.set_content_opacity(base)
        anim.start()

    def finish_island_anim(self):
        self.island_anim = None
        if self.island_on():
            self.apply_island_state()
            if self.island_open:
                self.place()
            else:
                self.move(self.collapse_rect().topLeft())

    def set_island_open(self, opened):
        if opened == self.island_open:
            return
        self.island_open = opened
        if self.island_on():
            self.animate_island(opened)
        else:
            self.apply_island_state()
            self.place()

    def sync_island(self):
        """Keep open/closed state and the real window size in agreement."""
        if not self.island_on():
            return
        wanted = self.hovered or self.app.island_pinned or self.app.menu_open()
        if wanted:
            self.collapse_timer.stop()
            if not self.island_open:
                self.set_island_open(True)
        elif self.island_open and not self.collapse_timer.isActive():
            self.collapse_timer.start(ISLAND_COLLAPSE_MS)
        if self.island_busy():
            return
        if self.snap_anim is not None:
            return
        collapsed = self.is_collapsed_size()
        if collapsed == self.island_open:  # state drifted from the window size
            self.apply_island_state()
            self.place()

    def maybe_collapse(self):
        if self.hovered or self.app.island_pinned or self.app.menu_open():
            return
        self.set_island_open(False)

    # -- motion --------------------------------------------------------------
    def animate_hover(self, inside):
        if self.hover_anim is not None:
            self.hover_anim.stop()
        anim = QVariantAnimation(self)
        anim.setDuration(HOVER_MS)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.setStartValue(self.hover_t)
        anim.setEndValue(1.0 if inside else 0.0)
        anim.valueChanged.connect(self.set_hover_t)
        self.hover_anim = anim
        anim.start()

    def set_hover_t(self, value):
        self.hover_t = float(value)
        self.sync_gear()
        self.update()

    def ripple(self):
        """A ring of the accent colour leaves the pill, and its border flares."""
        if self.wave_anim is not None:
            self.wave_anim.stop()
        anim = QVariantAnimation(self)
        anim.setDuration(WAVE_MS)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)

        def step(value):
            self.wave_t = float(value)
            self.shadow.update()
            self.update()

        anim.valueChanged.connect(step)
        anim.finished.connect(lambda: step(1.0))
        self.wave_anim = anim
        anim.start()

    def sync_gear(self):
        """The gear fades in step with the border and spins into place with a little overshoot."""
        self.gear_effect.setOpacity(max(0.0, min(1.0, self.hover_t)))
        self.gear.angle = QEasingCurve(QEasingCurve.OutBack).valueForProgress(self.hover_t) * 150
        self.gear.update()

    def cascade(self):
        """Numbers drop in one after another."""
        for index, reading in enumerate(self.readings):
            reading.enter(70 + 55 * index)

    def pulse_running(self):
        return self.pulse_anim is not None and self.pulse_anim.state() == QAbstractAnimation.Running

    def sync_pulse(self):
        """Breathe only while a critical value is actually on screen."""
        shown = self.isVisible() and (self.island_open or not self.island_on())
        wanted = (shown and bool(self.app.config.get("pulse"))
                  and any(reading.critical for reading in self.readings))
        if wanted and not self.pulse_running():
            anim = QVariantAnimation(self)
            anim.setDuration(PULSE_MS)
            anim.setLoopCount(-1)
            anim.setEasingCurve(QEasingCurve.InOutSine)
            anim.setKeyValueAt(0.0, 0.0)
            anim.setKeyValueAt(0.5, 1.0)
            anim.setKeyValueAt(1.0, 0.0)
            anim.valueChanged.connect(self.set_pulse_value)
            self.pulse_anim = anim
            anim.start()
        elif not wanted and self.pulse_running():
            self.pulse_anim.stop()
            self.set_pulse_value(0.0)

    def set_pulse_value(self, value):
        self.pulse_value = float(value)
        for reading in self.readings:
            if reading.critical:
                reading.update()

    # -- window follow -------------------------------------------------------
    def moveEvent(self, event):
        super().moveEvent(event)
        self.shadow.follow()

    def showEvent(self, event):
        super().showEvent(event)
        self.shadow.follow()
        self.shadow.show()
        self.cascade()
        QTimer.singleShot(0, self.raise_)  # shadow first, pill on top of it

    def hideEvent(self, event):
        super().hideEvent(event)
        self.shadow.hide()
        self.sync_pulse()

    # -- interaction ---------------------------------------------------------
    def poll_hover(self):
        if self.drag_offset is not None and QGuiApplication.mouseButtons() == Qt.NoButton:
            self.drag_offset = None
            self.drag_started = False
        cursor = QCursor.pos()
        inside = self.frameGeometry().contains(cursor)
        for reading in self.readings:
            area = QRect(reading.mapToGlobal(QPoint(0, 0)), reading.size()).adjusted(-5, -4, 5, 4)
            reading.set_hot(inside and reading.isVisible() and area.contains(cursor))
        if inside != self.hovered:
            self.hovered = inside
            self.animate_hover(inside)
        self.sync_island()
        self.sync_pulse()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_offset = event.globalPosition().toPoint() - self.pos()
            self.drag_origin = event.globalPosition().toPoint()
            self.drag_started = False
            self.grabMouse()
            event.accept()
        elif event.button() == Qt.RightButton:
            self.show_menu()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_offset is not None:
            point = event.globalPosition().toPoint()
            if not self.drag_started:
                delta = point - self.drag_origin
                if abs(delta.x()) < 3 and abs(delta.y()) < 3:
                    return
                self.drag_started = True
            self.move(point - self.drag_offset)  # an island drags freely, then snaps to an edge
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def snap_to_island(self, duration=300):
        """Glide to the docked rectangle (new edge, new corner, or just back in place)."""
        if self.snap_anim is not None:
            self.snap_anim.stop()
            self.snap_anim = None
        if self.island_anim is not None:
            self.island_anim.stop()
            self.island_anim = None
        if self.box.direction() != (QBoxLayout.TopToBottom if self.side_docked()
                                    else QBoxLayout.LeftToRight):
            self.build()  # the edge changed between horizontal and vertical
        target = self.expanded_rect() if self.island_open else self.collapse_rect()
        start = self.geometry()
        if start == target:
            self.apply_island_state()
            return
        if self.island_open:
            self.fit_content()
        self.setMinimumSize(0, 0)
        self.setMaximumSize(MAX_WIDGET_SIZE, MAX_WIDGET_SIZE)
        curve = QEasingCurve(QEasingCurve.OutBack)
        curve.setOvershoot(0.9)

        def lerp(a, b, t):
            return round(a + (b - a) * t)

        def step(raw):
            t = curve.valueForProgress(raw)
            self.setGeometry(QRect(lerp(start.x(), target.x(), t), lerp(start.y(), target.y(), t),
                                   lerp(start.width(), target.width(), t),
                                   lerp(start.height(), target.height(), t)))
            self.center_content()

        def done():
            self.snap_anim = None
            self.setGeometry(target)
            self.apply_island_state()
            self.place()

        anim = QVariantAnimation(self)
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.valueChanged.connect(step)
        anim.finished.connect(done)
        self.snap_anim = anim
        anim.start()

    def mouseReleaseEvent(self, event):
        if self.drag_offset is not None:
            moved = self.drag_started
            self.drag_offset = None
            self.drag_started = False
            self.releaseMouse()
            if moved:
                if self.island_on():
                    self.app.remember_island(self)
                else:
                    self.app.remember_position(self)
            elif self.island_on() and event.button() == Qt.LeftButton:
                self.app.toggle_island_pinned()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    # -- placement -----------------------------------------------------------
    def key(self):
        return self.screen.name() or str(self.screen_index)

    def place(self, force=False):
        if self.island_busy():
            return
        area = self.screen.availableGeometry()
        box = (area.x(), area.y(), area.width(), area.height())
        if self.island_on():
            if self.snap_anim is not None:
                return
            if self.island_open:
                target = self.expanded_rect()
            else:
                target = self.collapse_rect()
            if self.pos() != target.topLeft():
                self.move(target.topLeft())
            return
        stored = None if force else self.app.config.positions.get(self.key())
        if stored:
            x, y = area.x() + stored[0], area.y() + stored[1]
        else:
            x, y = core.anchored_position(
                box, self.width(), self.height(), self.app.config.get("anchor"))
        seams = core.seam_edges(self.screen_index, self.app.screen_geometries())
        x, y = core.clamp_to_area(x, y, self.width(), self.height(),
                                  (area.x(), area.y(), area.width(), area.height()),
                                  core.MARGIN, seams)
        if self.pos() != QPoint(int(x), int(y)):
            self.move(int(x), int(y))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.shadow.follow()
        self.center_content()
        # adjustSize() finishes after the layout runs, so re-anchor here with the
        # real width instead of the previous one.
        if self.drag_offset is None and not self.island_busy():
            QTimer.singleShot(0, self.place)

    def rebuild(self):
        self.css = SIZES[self.app.config.get("size")]
        self.box.setContentsMargins(self.css["pad_h"], self.css["pad_v"],
                                    max(2, self.css["pad_h"] - 2), self.css["pad_v"])
        self.box.setSpacing(self.css["gap"])
        self.build()
        self.shadow.update()

    def set_rows(self, rows):
        self.rows = rows
        self.build()

    def update_system(self):
        if not self.system_labels:
            return
        for name, reading in self.app.metrics.snapshot():
            label = self.system_labels.get(name)
            if label is not None and reading is not None:
                label.set_reading(f"{reading}%", reading, self.reading_colors(reading))
        self.sync_pulse()

    def show_menu(self):
        self.app.popup_menu(self)

    def fade_visibility(self, visible):
        """Fade the pill and its shadow in or out; hiding happens once the fade is done."""
        if self.vis_anim is not None:
            self.vis_anim.stop()
        start = self.windowOpacity() if self.isVisible() else 0.0
        if visible:
            self.setWindowOpacity(start)
        anim = QVariantAnimation(self)
        anim.setDuration(SHOW_MS)
        anim.setEasingCurve(QEasingCurve.OutCubic if visible else QEasingCurve.InCubic)
        anim.setStartValue(float(start))
        anim.setEndValue(1.0 if visible else 0.0)

        def step(value):
            self.setWindowOpacity(float(value))
            self.shadow.setWindowOpacity(float(value))

        def done():
            self.vis_anim = None
            if not visible and self.app.hidden:
                self.hide()
            self.setWindowOpacity(1.0)
            self.shadow.setWindowOpacity(1.0)

        anim.valueChanged.connect(step)
        anim.finished.connect(done)
        self.vis_anim = anim
        anim.start()


# ------------------------------------------------------------------------------ app

class VigIA(QObject):
    data_ready = Signal(dict)
    source_ready = Signal(str)   # ai-usagebar version once VigIA has its own copy

    def __init__(self, app):
        super().__init__()
        self.qt = app
        self.config = core.Config()
        self.metrics = core.SystemMetrics()
        self.windows = []
        self.rows = []
        self.report = {}
        self.hidden = False
        self.refreshing = False
        self.island_pinned = False
        self.last_fetch = 0.0
        self.hotkey = None
        self.server = None
        self.data_ready.connect(self.apply_report)
        self.source_ready.connect(self.on_source)
        self.source_version = ''
        self.updating_source = False

        core.set_theme(self.config.get("theme"), self.system_is_dark(),
                       self.config.get("accent"))
        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(
                lambda *_: self.config.get("theme") == "auto" and self.apply_theme())
        self.start_hotkey()
        self.rebuild_windows()
        self.start_server()
        self.autostart()
        self.trigger_refresh()
        QTimer.singleShot(2000, self.start_timers)
        threading.Thread(target=self.probe_source, daemon=True).start()
        QGuiApplication.instance().screenAdded.connect(lambda *_: self.rebuild_windows())
        QGuiApplication.instance().screenRemoved.connect(lambda *_: self.rebuild_windows())

    def start_timers(self):
        self.system_timer = QTimer(self)
        self.system_timer.timeout.connect(self.system_tick)
        self.system_timer.start(2000)
        self.provider_timer = QTimer(self)
        self.provider_timer.timeout.connect(self.provider_tick)
        self.provider_timer.start(30_000)

    # -- environment ---------------------------------------------------------
    def screens(self):
        return QGuiApplication.screens()

    def primary_index(self):
        primary = QGuiApplication.primaryScreen()
        for index, screen in enumerate(self.screens()):
            if screen is primary:
                return index
        return 0

    def screen_geometries(self):
        result = []
        for screen in self.screens():
            geometry = screen.geometry()
            result.append((geometry.x(), geometry.y(), geometry.width(), geometry.height()))
        return result

    def monitor_indices(self):
        count = len(self.screens())
        choice = str(self.config.get("monitor"))
        if choice == "all":
            return list(range(count))
        if choice == "secondary":
            primary = self.primary_index()
            others = [index for index in range(count) if index != primary]
            return others[:1] or [primary]
        if choice.isdigit():  # legacy config: index -> screen name
            index = int(choice)
            if index < count:
                name = self.screens()[index].name()
                if name:
                    self.config.set("monitor", name)
                    return [index]
            return [self.primary_index()]
        for index, screen in enumerate(self.screens()):
            if screen.name() == choice:
                return [index]
        core.log(f"monitor {choice!r} not found; using primary")
        return [self.primary_index()]

    def hidden_items(self, key):
        return {item.strip().lower() for item in str(self.config.get(key)).split(",") if item.strip()}

    def set_hidden(self, key, values):
        self.config.set(key, ",".join(sorted(values)))

    def apply_rows(self):
        for window in self.windows:
            window.set_rows(self.rows)

    def toggle_provider(self, provider_id, checked):
        hidden = self.hidden_items("hide_providers")
        if checked:
            hidden.discard(provider_id.lower())
        else:
            hidden.add(provider_id.lower())
        self.set_hidden("hide_providers", hidden)
        self.apply_rows()

    def toggle_system(self, name, checked):
        hidden = self.hidden_items("hide_system")
        if checked:
            hidden.discard(name.lower())
        else:
            hidden.add(name.lower())
        self.set_hidden("hide_system", hidden)
        self.apply_rows()

    def effective_alpha(self, hovered=False):
        return min(1.0, self.config.get("opacity") + (0.10 if hovered else 0.0))

    # -- windows -------------------------------------------------------------
    def rebuild_windows(self):
        """Keep existing pills alive; only add/remove what the monitor choice needs.

        Recreating a window closes an open settings menu, so staying incremental
        is what lets the menu survive a change.
        """
        wanted = self.monitor_indices()
        existing = {window.screen_index: window for window in self.windows}
        for index, window in list(existing.items()):
            if index not in wanted:
                window.close()
                window.deleteLater()
                del existing[index]
        for index in wanted:
            window = existing.get(index)
            if window is None:
                window = Pill(self, index)
                existing[index] = window
            else:
                window.screen = self.screens()[index]
            window.set_rows(self.rows)
            if self.hidden:
                window.hide()
            else:
                window.show()
        self.windows = [existing[index] for index in wanted]
        for window in self.windows:
            window.place()

    def autostart(self):
        core.set_autostart(self.config.get("autostart"), self.command_line())

    def command_line(self):
        executable = sys.executable
        if core.IS_WINDOWS:
            pythonw = os.path.join(os.path.dirname(executable), "pythonw.exe")
            if os.path.isfile(pythonw):
                executable = pythonw
        return f'"{executable}" "{os.path.realpath(sys.argv[0])}"'

    # -- data ----------------------------------------------------------------
    def trigger_refresh(self):
        if self.refreshing:
            return
        self.refreshing = True
        threading.Thread(target=self.fetch, daemon=True).start()

    def probe_source(self, force=False):
        """Background: make sure VigIA has its own ai-usagebar, then report its version."""
        try:
            binary = core.ensure_usagebar(force=force) or core.installed_binary(
                "ai-usagebar", override=os.environ.get("AI_USAGEBAR_BIN"))
            self.source_ready.emit(core.usagebar_version(binary))
        except Exception as error:
            core.log(f"source probe failed: {error}")
            self.source_ready.emit("")

    def on_source(self, version):
        was_updating, self.updating_source = self.updating_source, False
        changed = version != self.source_version
        self.source_version = version
        if was_updating:
            for window in self.windows:
                window.ripple()  # the data source was refreshed: same ring as a colour change
            self.last_fetch = 0.0
            self.trigger_refresh()
            core.log(f"data source updated: ai-usagebar {version}")

    def update_source(self):
        """Menu action: fetch the newest ai-usagebar release when the installed one is older."""
        if self.updating_source:
            return
        self.updating_source = True

        def work():
            latest = core.latest_usagebar_version()
            current = self.source_version
            newer = latest and (not current or tuple(map(int, latest.split("."))) >
                                tuple(map(int, current.split("."))))
            self.probe_source(force=bool(newer))

        threading.Thread(target=work, daemon=True).start()

    def fetch(self):
        try:
            report = core.fetch_report()
            self.data_ready.emit(report)
        except Exception as error:  # keep the pill alive with the last good data
            core.log(f"usage fetch failed: {error}")
            self.refreshing = False

    def apply_report(self, report):
        self.report = report or {}
        self.last_fetch = time.monotonic()
        self.refreshing = False
        self.refresh_rows()

    def refresh_rows(self):
        self.rows = core.provider_rows(
            self.report, self.config.get("max_providers"), self.config.metrics)
        self.apply_rows()

    def system_tick(self):
        if not self.config.get("show_system"):
            return
        for window in self.windows:
            window.update_system()

    def provider_tick(self):
        if time.monotonic() - self.last_fetch >= self.config.get("refresh_minutes") * 60:
            self.trigger_refresh()

    # -- menu ----------------------------------------------------------------
    def popup_menu(self, anchor=None, pos=None, open_key=None):
        menu = StickyMenu(parent=anchor)
        self.menu_anchor = anchor
        menu.setStyleSheet(menu_qss())
        self.menu = menu

        header = menu.addAction(
            f"{core.APP_NAME}   ·   {self.config.t('hotkey_hint', accel=self.accelerator_label())}")
        header.setEnabled(False)
        menu.addSeparator()

        opacity = self.submenu(menu, self.config.t("menu_opacity"))
        group = QActionGroup(opacity)
        group.setExclusive(True)
        current = round(self.config.get("opacity") * 100)
        for step in (100, 90, 80, 70, 60, 50, 40):
            action = QAction(f"{step}%", opacity)
            action.setCheckable(True)
            action.setChecked(step == current)
            action.triggered.connect(lambda _=False, value=step: self.set_opacity(value))
            group.addAction(action)
            opacity.addAction(action)

        size_menu = self.submenu(menu, self.config.t("menu_size"))
        group = QActionGroup(size_menu)
        for key, label in (("small", self.config.t("size_small")),
                           ("medium", self.config.t("size_medium")),
                           ("large", self.config.t("size_large"))):
            action = QAction(label, size_menu)
            action.setCheckable(True)
            action.setChecked(key == self.config.get("size"))
            action.triggered.connect(lambda _=False, value=key: self.set_size(value))
            group.addAction(action)
            size_menu.addAction(action)

        theme_menu = self.submenu(menu, self.config.t("menu_theme"))
        group = QActionGroup(theme_menu)
        for key, label in ([("auto", self.config.t("theme_auto"))] + core.list_themes()):
            action = QAction(label, theme_menu)
            action.setCheckable(True)
            action.setChecked(key == self.config.get("theme"))
            action.triggered.connect(lambda _=False, value=key: self.set_theme(value))
            group.addAction(action)
            theme_menu.addAction(action)
        theme_menu.addSeparator()
        accent_menu = self.submenu(theme_menu, self.config.t("accent_pick").rstrip("…").strip())
        picker = AccentPicker(core.THEME["primary"])
        picker.previewed.connect(lambda color: self.apply_theme(color))
        picker.committed.connect(self.set_accent)
        holder = QWidgetAction(accent_menu)
        holder.setDefaultWidget(picker)
        accent_menu.addAction(holder)
        accent_menu.addSeparator()
        reset = accent_menu.addAction(self.config.t("accent_reset"))
        reset.triggered.connect(lambda: (
            self.set_accent(""),
            QTimer.singleShot(THEME_MS + 40, lambda: picker.set_color(core.THEME["primary"]))))

        icons_menu = self.submenu(menu, self.config.t("menu_icons"))
        group = QActionGroup(icons_menu)
        for key, label in (("brand", self.config.t("icons_brand")),
                           ("mono", self.config.t("icons_mono")),
                           ("alert", self.config.t("icons_alert"))):
            action = QAction(label, icons_menu)
            action.setCheckable(True)
            action.setChecked(key == self.config.get("icon_style"))
            action.triggered.connect(lambda _=False, value=key: self.set_icon_style(value))
            group.addAction(action)
            icons_menu.addAction(action)

        items_menu = self.submenu(menu, self.config.t("menu_items"))
        hidden_providers = self.hidden_items("hide_providers")
        for row in self.rows:
            action = QAction(row["name"], items_menu)
            action.setCheckable(True)
            action.setChecked(row["id"].lower() not in hidden_providers)
            action.toggled.connect(
                lambda checked, pid=row["id"]: self.toggle_provider(pid, checked))
            items_menu.addAction(action)
        missing = sorted(hidden_providers - {row["id"].lower() for row in self.rows})
        for provider_id in missing:
            action = QAction(provider_id, items_menu)
            action.setCheckable(True)
            action.setChecked(False)
            action.toggled.connect(
                lambda checked, pid=provider_id: self.toggle_provider(pid, checked))
            items_menu.addAction(action)
        items_menu.addSeparator()
        hidden_system = self.hidden_items("hide_system")
        for name in ("CPU", "RAM", "GPU"):
            action = QAction(name, items_menu)
            action.setCheckable(True)
            action.setChecked(name.lower() not in hidden_system)
            action.toggled.connect(
                lambda checked, key=name: self.toggle_system(key, checked))
            items_menu.addAction(action)

        watch_menu = self.submenu(menu, self.config.t("menu_metric"))
        for entry in core.dashboard_entries(self.report):
            provider_id = str(entry.get("id") or entry.get("brand") or "")
            metrics = core.quota_metrics(entry)
            if not metrics:
                continue
            provider_menu = self.submenu(
                watch_menu, str(entry.get("display_name") or entry.get("name") or provider_id))
            group = QActionGroup(provider_menu)
            choice = self.config.metric_choice(provider_id)
            chosen = None if choice == "auto" else core.matching_metric(entry, choice)
            auto = QAction(self.config.t("metric_auto"), provider_menu)
            auto.setCheckable(True)
            auto.setChecked(chosen is None)
            auto.triggered.connect(
                lambda _=False, pid=provider_id: self.set_metric(pid, "auto"))
            group.addAction(auto)
            provider_menu.addAction(auto)
            provider_menu.addSeparator()
            for metric in metrics:
                label = metric.get("label") or "—"
                action = QAction(f"{label} — {core.metric_display(metric)}", provider_menu)
                action.setCheckable(True)
                action.setChecked(chosen is metric)
                action.triggered.connect(
                    lambda _=False, pid=provider_id, value=label: self.set_metric(pid, value))
                group.addAction(action)
                provider_menu.addAction(action)

        if watch_menu.isEmpty():
            waiting = watch_menu.addAction(self.config.t("metric_waiting"))
            waiting.setEnabled(False)

        monitor_menu = self.submenu(menu, self.config.t("menu_monitor"))
        group = QActionGroup(monitor_menu)
        options = [("primary", self.config.t("monitor_primary")),
                   ("secondary", self.config.t("monitor_secondary")),
                   ("all", self.config.t("monitor_all"))]
        for index, screen in enumerate(self.screens()):
            options.append((screen.name() or str(index),
                            self.config.t("monitor_screen", n=index + 1)))
        for key, label in options:
            action = QAction(label, monitor_menu)
            action.setCheckable(True)
            action.setChecked(key == self.config.get("monitor"))
            action.triggered.connect(lambda _=False, value=key: self.set_monitor(value))
            group.addAction(action)
            monitor_menu.addAction(action)

        if self.config.get("island"):
            self.island_position_menu(menu)
        else:
            anchor_menu = self.submenu(menu, self.config.t("menu_anchor"))
            group = QActionGroup(anchor_menu)
            for key, label_key in core.ANCHORS.items():
                action = QAction(self.config.t(label_key), anchor_menu)
                action.setCheckable(True)
                action.setChecked(key == self.config.get("anchor"))
                action.triggered.connect(lambda _=False, value=key: self.set_anchor(value))
                group.addAction(action)
                anchor_menu.addAction(action)

        language_menu = self.submenu(menu, self.config.t("menu_language"))
        group = QActionGroup(language_menu)
        choices = [("auto", self.config.t("language_auto"))] + list(core.LANGUAGES.items())
        for key, label in choices:
            action = QAction(label, language_menu)
            action.setCheckable(True)
            action.setChecked(key == self.config.get("language"))
            action.triggered.connect(lambda _=False, value=key: self.set_language(value))
            group.addAction(action)
            language_menu.addAction(action)

        menu.addSeparator()

        source = menu.addAction(self.config.t("menu_source_update",
                                              version=self.source_version or "…"))
        source.triggered.connect(self.update_source)
        menu.addSeparator()

        island = QAction(self.config.t("menu_island"), menu)
        island.setCheckable(True)
        island.setChecked(self.config.get("island"))
        island.toggled.connect(self.set_island)
        menu.addAction(island)

        top = QAction(self.config.t("always_on_top"), menu)
        top.setCheckable(True)
        top.setChecked(self.config.get("always_on_top"))
        top.toggled.connect(self.set_always_on_top)
        menu.addAction(top)

        system = QAction(self.config.t("show_system"), menu)
        system.setCheckable(True)
        system.setChecked(self.config.get("show_system"))
        system.toggled.connect(self.set_show_system)
        menu.addAction(system)

        bars = QAction(self.config.t("menu_bars"), menu)
        bars.setCheckable(True)
        bars.setChecked(self.config.get("bars"))
        bars.toggled.connect(self.set_bars)
        menu.addAction(bars)

        pulse = QAction(self.config.t("menu_pulse"), menu)
        pulse.setCheckable(True)
        pulse.setChecked(self.config.get("pulse"))
        pulse.toggled.connect(self.set_pulse)
        menu.addAction(pulse)

        autostart = QAction(self.config.t("autostart"), menu)
        autostart.setCheckable(True)
        autostart.setChecked(self.config.get("autostart"))
        autostart.toggled.connect(self.set_autostart)
        menu.addAction(autostart)

        menu.addSeparator()
        menu.addAction(self.config.t("refresh_now"), self.trigger_refresh)
        menu.addAction(self.config.t("open_config"), self.open_config)
        menu.addAction(self.config.t("reset_position"), self.reset_position)
        hide = menu.addAction(self.config.t("hide"), self.hide_all)
        hide.setProperty("closes_menu", True)
        quit_action = menu.addAction(self.config.t("quit"), self.quit)
        quit_action.setProperty("closes_menu", True)
        menu.addSeparator()
        version = menu.addAction(f"{core.APP_NAME} v{core.VERSION}")
        version.setEnabled(False)

        if open_key:  # re-opened after a language change: unfold the same submenu again
            target = next((action for action in menu.actions()
                           if action.menu() is not None
                           and action.text() == self.config.t(open_key)), None)
            if target is not None:
                QTimer.singleShot(60, lambda: menu.setActiveAction(target))
        menu.exec(pos or QCursor.pos())

    # -- settings ------------------------------------------------------------
    def set_opacity(self, value):
        self.config.set("opacity", value / 100.0)
        for window in self.windows:
            window.update()

    def set_size(self, value):
        self.config.set("size", value)
        for window in self.windows:
            window.rebuild()

    def system_is_dark(self):
        hints = QGuiApplication.styleHints()
        scheme = getattr(hints, "colorScheme", None)
        return scheme is None or scheme() != Qt.ColorScheme.Light

    def apply_theme(self, accent=None, ripple=True):
        """Cross-fade to the configured theme: pills and any open menu follow every frame.

        `accent` previews a colour that is not saved (the accent picker)."""
        old = dict(core.THEME)
        core.set_theme(self.config.get("theme"), self.system_is_dark(),
                       self.config.get("accent") if accent is None else accent)
        new = dict(core.THEME)
        anim = getattr(self, "theme_anim", None)
        if anim is not None:
            anim.stop()
        if ripple and accent is None:
            for window in self.windows:
                window.ripple()
        if old == new:
            return
        # Only plain #rrggbb values blend; anything else (alpha forms) lands with the theme.
        plain = [k for k in new if k in old and len(new[k]) == 7 and len(old[k]) == 7]
        start = {k: QColor(old[k]) for k in plain}
        end = {k: QColor(new[k]) for k in plain}

        def frame(t):
            for key, color in end.items():
                core.THEME[key] = mix(start[key], color, t).name()
            self.restyle_all()
            if t >= 1.0:
                core.THEME.update(new)  # land exactly on the theme's own values
                self.restyle_all()

        self.theme_anim = anim = QVariantAnimation(self)
        anim.setDuration(THEME_MS)
        anim.setEasingCurve(QEasingCurve.InOutCubic)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.valueChanged.connect(frame)
        anim.start()

    def restyle_all(self):
        for window in self.windows:
            window.restyle()
        menu = getattr(self, "menu", None)
        if menu is not None and menu.isVisible():
            qss = menu_qss()
            for each in [menu] + menu.findChildren(QMenu):
                each.setStyleSheet(qss)

    def set_accent(self, value):
        self.config.set("accent", value)
        self.apply_theme()

    def set_bars(self, enabled):
        self.config.set("bars", enabled)
        for window in self.windows:
            window.rebuild()

    def set_pulse(self, enabled):
        self.config.set("pulse", enabled)
        for window in self.windows:
            window.sync_pulse()

    def set_theme(self, value):
        self.config.set("theme", value)
        self.apply_theme()

    def set_icon_style(self, value):
        self.config.set("icon_style", value)
        for window in self.windows:
            window.rebuild()

    def set_monitor(self, value):
        self.config.set("monitor", value)
        self.rebuild_windows()

    def island_position_menu(self, menu):
        """Edge x position along it: the island's own 12 docking spots, grouped by edge."""
        position_menu = self.submenu(menu, self.config.t("menu_island_position"))
        group = QActionGroup(position_menu)
        current = self.config.get("island_anchor")
        previous_edge = None
        for key in core.ISLAND_ANCHORS:
            edge, along = key.split("-", 1)
            if previous_edge is not None and edge != previous_edge:
                position_menu.addSeparator()
            previous_edge = edge
            label = f"{self.config.t('island_' + edge)} · {self.config.t('along_' + along)}"
            action = QAction(label, position_menu)
            action.setCheckable(True)
            action.setChecked(key == current)
            action.triggered.connect(lambda _=False, value=key: self.set_island_anchor(value))
            group.addAction(action)
            position_menu.addAction(action)

    def set_anchor(self, value):
        self.config.set("anchor", value)
        self.config.positions = {}
        self.config.save()
        for window in self.windows:
            window.place(force=True)

    def set_metric(self, provider_id, choice):
        """Pick which limit of a provider the pill shows ("auto" = most used)."""
        self.config.set_metric(provider_id, choice)
        self.refresh_rows()

    def set_language(self, value):
        self.config.set("language", value)
        for window in self.windows:
            window.rebuild()
        self.reopen_menu("menu_language")

    def reopen_menu(self, open_key=None):
        """The popup was built in the old language: rebuild it in place, same spot."""
        menu = getattr(self, "menu", None)
        if menu is None or not menu.isVisible():
            return
        pos, anchor = menu.pos(), getattr(self, "menu_anchor", None)
        menu.close_chain()
        QTimer.singleShot(0, lambda: self.popup_menu(anchor, pos, open_key))

    def set_island(self, enabled):
        """Dock the pills to a screen edge (or release them back to the anchor)."""
        self.config.set("island", enabled)
        if not enabled:
            self.island_pinned = False
        for window in self.windows:
            window.collapse_timer.stop()
            if window.island_anim is not None:
                window.island_anim.stop()
                window.island_anim = None
            window.island_open = False
            window.apply_island_state()
            window.place()
        self.reopen_menu()  # the position submenu differs between the two modes

    def island_offset(self, window):
        return int(self.config.island_offsets.get(str(window.key()), 0))

    def remember_island(self, window):
        """After a drag: dock to the nearest edge, keep where along it the island was dropped."""
        area = window.screen.availableGeometry()
        frame = window.geometry()
        gaps = {"left": frame.left() - area.left(), "right": area.right() - frame.right(),
                "top": frame.top() - area.top(), "bottom": area.bottom() - frame.bottom()}
        edge = min(gaps, key=gaps.get)
        if edge in ("top", "bottom"):
            anchor, offset = f"{edge}-center", frame.center().x() - area.center().x()
            limit = max(0, (area.width() - frame.width()) // 2)
        else:
            anchor, offset = f"{edge}-middle", frame.center().y() - area.center().y()
            limit = max(0, (area.height() - frame.height()) // 2)
        self.config.set("island_anchor", anchor)
        self.config.island_offsets = {str(window.key()): max(-limit, min(int(offset), limit))}
        self.config.save()
        for each in self.windows:
            each.snap_to_island(300 if each is window else 360)

    def set_island_anchor(self, value):
        """Menu choice: dock to an edge/corner; offsets from earlier drags no longer apply."""
        self.config.set("island_anchor", value)
        self.config.island_offsets = {}
        self.config.save()
        for window in self.windows:
            window.snap_to_island(380)

    def toggle_island_pinned(self):
        """A click on the island pins it open; another click lets it collapse."""
        self.island_pinned = not self.island_pinned
        for window in self.windows:
            window.sync_island()
        core.log(f"island pinned: {self.island_pinned}")

    def accelerator_label(self):
        return pretty_accelerator(getattr(self.hotkey, "accelerator", ""))

    def menu_open(self):
        menu = getattr(self, "menu", None)
        return menu is not None and menu.isVisible()

    def set_always_on_top(self, enabled):
        self.config.set("always_on_top", enabled)
        for window in self.windows:
            window.setWindowFlag(Qt.WindowStaysOnTopHint, enabled)
            window.show()
            window.place()

    def set_show_system(self, enabled):
        self.config.set("show_system", enabled)
        for window in self.windows:
            window.rebuild()

    def set_autostart(self, enabled):
        self.config.set("autostart", enabled)
        core.set_autostart(enabled, self.command_line())

    def submenu(self, parent, title):
        sub = StickyMenu(parent=parent)
        sub.setTitle(title)
        sub.setStyleSheet(menu_qss())
        parent.addMenu(sub)
        return sub

    def open_config(self):
        try:
            if core.IS_WINDOWS:
                os.startfile(core.CONFIG_PATH)  # noqa: S606
            else:
                subprocess.Popen(["xdg-open", core.CONFIG_PATH])
        except OSError as error:
            core.log(f"open config failed: {error}")

    def reset_position(self):
        self.config.positions = {}
        self.config.island_offsets = {}
        self.config.set("island_anchor", core.DEFAULTS["island_anchor"])
        self.config.save()
        for window in self.windows:
            if window.island_on():
                window.snap_to_island(380)
            else:
                window.place(force=True)

    def remember_position(self, window):
        point = window.frameGeometry().center()
        screen = QGuiApplication.screenAt(point) or window.screen
        area = screen.availableGeometry()
        index = self.screens().index(screen) if screen in self.screens() else 0
        x, y = core.clamp_to_area(window.x(), window.y(), window.width(), window.height(),
                                  (area.x(), area.y(), area.width(), area.height()),
                                  core.MARGIN, core.seam_edges(index, self.screen_geometries()))
        if (x, y) != (window.x(), window.y()):
            window.move(x, y)
        if index != window.screen_index:
            # the pill changed screens: remember it there and keep following that one
            window.screen_index = index
            window.screen = screen
            if str(self.config.get("monitor")) != "all":
                self.config.set("monitor", screen.name() or str(index))
        self.config.positions[window.key()] = (x - area.x(), y - area.y())
        self.config.save()
        core.log(f"moved to {screen.name()} at {x},{y}")

    # -- visibility ----------------------------------------------------------
    def hide_all(self):
        self.hidden = True
        for window in self.windows:
            window.fade_visibility(False)

    def show_all(self):
        self.hidden = False
        for window in self.windows:
            window.show()
            window.place()
            window.fade_visibility(True)

    def toggle(self):
        if self.hidden:
            self.show_all()
        else:
            self.hide_all()

    def quit(self):
        QApplication.quit()

    # -- hotkey --------------------------------------------------------------
    def start_hotkey(self):
        self.hotkey = Hotkey(self.config.get("hotkey"))
        self.hotkey.triggered.connect(self.toggle)
        self.hotkey.start()

    # -- ipc -----------------------------------------------------------------
    def start_server(self):
        QLocalServer.removeServer(SERVER_NAME)
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self.on_connection)
        if not self.server.listen(SERVER_NAME):
            core.log(f"ipc listen failed: {self.server.errorString()}")

    def on_connection(self):
        socket = self.server.nextPendingConnection()
        if socket is None:
            return
        socket.waitForReadyRead(300)
        command = bytes(socket.readAll()).strip()
        if command == b"TOGGLE":
            self.toggle()
        elif command == b"SHOW":
            self.show_all()
        elif command == b"HIDE":
            self.hide_all()
        elif command == b"REFRESH":
            self.trigger_refresh()
        elif command == b"RELOAD":
            self.reload_config()
        elif command == b"QUIT":
            QApplication.quit()
        socket.disconnectFromServer()

    def reload_config(self):
        previous = self.config.get("hotkey")
        self.config.load()
        if self.config.get("hotkey") != previous:
            core.log("hotkey changes need a restart")
        self.rebuild_windows()


# ------------------------------------------------------------------------------ cli

def send(command, timeout=300):
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if not socket.waitForConnected(timeout):
        return False
    socket.write(command.encode())
    socket.waitForBytesWritten(timeout)
    socket.disconnectFromServer()
    return True


def spawn_detached():
    executable = sys.executable
    if core.IS_WINDOWS:
        pythonw = os.path.join(os.path.dirname(executable), "pythonw.exe")
        if os.path.isfile(pythonw):
            executable = pythonw
    options = {"close_fds": True, "stdin": subprocess.DEVNULL,
               "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if core.IS_WINDOWS:
        options["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    subprocess.Popen([executable, os.path.realpath(sys.argv[0])], **options)


def main(argv=None):
    argv = sys.argv if argv is None else argv
    if "--version" in argv or "-v" in argv:
        print(f"{core.APP_NAME} {core.VERSION}")
        return 0
    if "--help" in argv or "-h" in argv:
        print(f"{core.APP_NAME} {core.VERSION} — AI usage and system metrics at a glance\n"
              "\n"
              "  vigia              run the pill (starts it if needed)\n"
              "  vigia --show       show it, starting the process if needed\n"
              "  vigia --toggle     show/hide (bind this to a shortcut)\n"
              "  vigia --reload     re-read the config file\n"
              "  vigia --quit       stop the running instance\n"
              "  vigia --version    print the version\n")
        return 0

    controls = {"--toggle": "TOGGLE", "--show": "SHOW", "--hide": "HIDE",
                "--quit": "QUIT", "--reload": "RELOAD"}
    requested = next((command for flag, command in controls.items() if flag in argv), None)
    if requested:
        QCoreApplication(argv)
        if send(requested):
            return 0
        if requested in ("TOGGLE", "SHOW"):
            spawn_detached()
            return 0
        return 1

    app = QApplication(argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(core.APP_NAME)
    app.setApplicationVersion(core.VERSION)

    if send("SHOW", 200):
        return 0

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    window_app = VigIA(app)
    if "--window" in argv:
        window_app.show_all()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
