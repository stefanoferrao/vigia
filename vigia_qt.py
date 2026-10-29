"""VigIA Qt shell — one interface for Linux and Windows.

Frameless, always-on-top pill with provider usage and optional CPU/RAM/GPU.
Everything platform-specific (paths, metrics, autostart) lives in vigia_core.
"""

import ctypes
import os
import signal
import subprocess
import sys
import threading
import time

from PySide6.QtCore import (QAbstractAnimation, QByteArray, QCoreApplication, QEasingCurve,
                            QEvent, QObject, QPoint, QPropertyAnimation, QRect, Qt,
                            QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import (
    QAction, QActionGroup, QColor, QCursor, QFont, QFontMetrics, QGuiApplication,
    QIcon, QPainter, QPainterPath, QPen, QPixmap,
)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QApplication, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QColorDialog, QMenu, QSizePolicy, QSpacerItem, QWidget)

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
ISLAND_EXPAND_MS = 340  # unfold: fast start, long soft landing
ISLAND_HIDE_MS = 240    # fold back: content leaves first, then the pill closes
MAX_WIDGET_SIZE = 16777215
FADE_MS = 220           # colour cross-fade when a reading changes state
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

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.pressed = True
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            pressed, self.pressed = self.pressed, False
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

    def set_reading(self, text, percent, colors):
        self.text = text
        self.percent = percent
        self.retarget(colors)
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

    def fade(self, start, t):
        self.tint = mix(start[0], self.target[0], t)
        self.bar = mix(start[1], self.target[1], t)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        width = self.width() - 2
        if self.bars and isinstance(self.percent, (int, float)):
            y = self.height() - self.BAR
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(core.THEME["divider"]))
            painter.drawRoundedRect(0, y, width, self.BAR, 1, 1)
            fill = round(width * max(0.0, min(100.0, self.percent)) / 100)
            if fill > 0:
                painter.setOpacity(self.pulse_opacity())
                painter.setBrush(self.bar)
                painter.drawRoundedRect(0, y, max(fill, self.BAR), self.BAR, 1, 1)
        painter.setOpacity(self.pulse_opacity())
        painter.setFont(self.font())
        painter.setPen(self.tint)
        painter.drawText(QRect(0, 0, self.width(), self.text_height),
                         Qt.AlignLeft | Qt.AlignVCenter, self.text)
        painter.end()

    def pulse_opacity(self):
        if self.critical and self.pill.pulse_running():
            return 1.0 - 0.35 * self.pill.pulse_value
        return 1.0


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
            path.addRoundedRect(ring, ring.height() / 2, ring.height() / 2)
            painter.fillPath(path, color)
        # Keep the pill itself clean: a translucent pill must not darken from below.
        painter.setCompositionMode(QPainter.CompositionMode_Clear)
        cut = QPainterPath()
        cut.addRoundedRect(inner, inner.height() / 2, inner.height() / 2)
        painter.fillPath(cut, Qt.transparent)
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
        self.system_labels = {}
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
        self.box = QHBoxLayout(self.content)
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
        self.hover_timer.start(120)
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
        self.system_labels = {}

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
        label.setStyleSheet(f"color: {core.THEME['text-secondary']};")
        label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        return label

    def divider(self):
        line = QWidget()
        line.setFixedSize(1, max(6, self.css["icon"] - 2))
        line.setStyleSheet(f"background: {core.THEME['divider']};")
        line.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        return line

    # -- rhythm --------------------------------------------------------------
    def add_gap(self, width):
        if width > 0:
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
        style = self.app.config.get("icon_style")
        dpr = self.devicePixelRatioF()

        hidden_providers = self.app.hidden_items("hide_providers")
        rows = [row for row in self.rows
                if row["id"].lower() not in hidden_providers][: self.app.config.get("max_providers")]
        if not rows:
            self.box.addWidget(self.muted_label("—"))
        for index, row in enumerate(rows):
            if index:
                self.add_gap(self.block_gap())
            tint = core.icon_tint(row["brand"], style)
            if not row["brand"] or not core.icon_path(row["brand"]):
                initials = QLabel(row["name"][:2].upper())
                font = QFont(initials.font())
                font.setPixelSize(self.css["font"])
                font.setBold(True)
                initials.setFont(font)
                initials.setStyleSheet(f"color: {core.THEME['text-secondary']};")
                initials.setFixedWidth(self.css["icon"] + 2)
                initials.setAlignment(Qt.AlignCenter)
                initials.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                self.box.addWidget(initials)
            else:
                pixmap = provider_pixmap(row["brand"], tint, self.css["icon"], dpr)
                icon = QLabel()
                icon.setPixmap(pixmap)
                icon.setFixedSize(self.css["icon"], self.css["icon"])
                icon.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                self.box.addWidget(icon)
            value = self.reading(f"provider:{row['id']}", row["value"], row["percent"])
            value.setToolTip(f"{row['name']} — {row['label']}" if row["label"] else row["name"])
            self.box.addWidget(value)

        if self.app.config.get("show_system"):
            hidden_system = self.app.hidden_items("hide_system")
            self.add_gap(self.group_gap())
            self.box.addWidget(self.divider())
            self.add_gap(self.group_gap())
            counted = 0
            for name, reading in self.app.metrics.snapshot():
                if reading is None or name.lower() in hidden_system:
                    continue
                if counted:
                    self.add_gap(self.block_gap())
                counted += 1
                self.box.addWidget(self.muted_label(name))
                value = self.reading(f"system:{name}", f"{reading}%", reading)
                self.box.addWidget(value)
                self.system_labels[name] = value

        self.add_gap(self.block_gap())
        self.gear = GearLabel(self.show_menu)
        self.gear.setPixmap(gear_pixmap(max(9, self.css["icon"] - 2), dpr))
        self.gear.setFixedSize(max(9, self.css["icon"] - 2), max(9, self.css["icon"] - 2))
        self.gear.setCursor(Qt.PointingHandCursor)
        self.gear.setToolTip(self.app.config.t("gear"))
        self.gear_effect = QGraphicsOpacityEffect(self.gear)
        self.gear_effect.setOpacity(1.0 if self.hovered else 0.0)
        self.gear.setGraphicsEffect(self.gear_effect)
        self.box.addWidget(self.gear)
        self.apply_island_state()

    # -- paint ---------------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(0, 0, -1, -1)
        radius = rect.height() / 2
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        alpha = self.app.effective_alpha(self.hovered)
        fill = QColor(core.THEME["surface"])
        fill.setAlpha(int(alpha * 255))
        painter.fillPath(path, fill)
        if fill.lightness() < 128 and rect.height() > ISLAND_HEIGHT + 2:
            # 1 px inner highlight along the top: a hint of depth on dark surfaces
            painter.setClipPath(path)
            painter.setPen(QPen(QColor(255, 255, 255, 18), 1))
            painter.drawLine(int(radius), 1, int(rect.width() - radius), 1)
            painter.setClipping(False)
        border = QColor(core.THEME["surface-border"])
        if self.hover_t > 0:
            accent = QColor(core.THEME["primary"])
            accent.setAlpha(190)
            border = mix(border, accent, self.hover_t)
        painter.setPen(QPen(border, 1))
        painter.drawPath(path)
        painter.end()

    # -- island --------------------------------------------------------------
    def island_on(self):
        return bool(self.app.config.get("island"))

    def collapse_rect(self):
        area = self.screen.availableGeometry()
        rect = QRect(area.x(), area.y(), ISLAND_WIDTH, ISLAND_HEIGHT)
        rect.moveLeft(core.island_x((area.x(), area.y(), area.width(), area.height()),
                                    ISLAND_WIDTH, self.app.island_offset(self)))
        return rect

    def expanded_rect(self, size=None):
        area = self.screen.availableGeometry()
        size = size or self.natural_size()
        rect = QRect(0, 0, size.width(), size.height())
        rect.moveLeft(core.island_x((area.x(), area.y(), area.width(), area.height()),
                                    size.width(), self.app.island_offset(self)))
        rect.moveTop(area.y())
        return rect

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
            self.setFixedSize(ISLAND_WIDTH, ISLAND_HEIGHT)
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
            self.show_children(True)
            self.fit_content()
            self.setMinimumSize(0, 0)
            self.setMaximumSize(MAX_WIDGET_SIZE, MAX_WIDGET_SIZE)
            end = self.expanded_rect()
            duration = ISLAND_EXPAND_MS
            curve = QEasingCurve(QEasingCurve.OutQuint)
        else:
            end = self.collapse_rect()
            duration = ISLAND_HIDE_MS
            curve = QEasingCurve(QEasingCurve.InOutCubic)
        if start == end:
            self.finish_island_anim()
            return
        # Interrupting a running fold/unfold: continue from the current opacity.
        base = (self.content_effect.opacity() if self.content_effect.isEnabled()
                else (0.0 if opened and start.height() <= ISLAND_HEIGHT else 1.0))

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
        collapsed = (self.width(), self.height()) == (ISLAND_WIDTH, ISLAND_HEIGHT)
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
        self.update()

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
        inside = self.frameGeometry().contains(QCursor.pos())
        if inside != self.hovered:
            self.hovered = inside
            self.gear_effect.setOpacity(1.0 if inside else 0.0)
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
            if self.island_on():
                self.move(point.x() - self.drag_offset.x(), self.y())
            else:
                self.move(point - self.drag_offset)
            event.accept()
        else:
            super().mouseMoveEvent(event)

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
            if self.island_open:
                target = self.expanded_rect()
            else:
                target = self.collapse_rect()
                if force:
                    target = QRect(area.x(), area.y(), ISLAND_WIDTH, ISLAND_HEIGHT)
                    target.moveLeft(core.island_x(box, ISLAND_WIDTH, 0))
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


# ------------------------------------------------------------------------------ app

class VigIA(QObject):
    data_ready = Signal(dict)

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
        pick = theme_menu.addAction(self.config.t("accent_pick"))
        pick.setProperty("closes_menu", True)
        pick.triggered.connect(lambda: QTimer.singleShot(0, self.pick_accent))
        if self.config.get("accent"):
            reset = theme_menu.addAction(self.config.t("accent_reset"))
            reset.triggered.connect(lambda: self.set_accent(""))

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

    def apply_theme(self):
        core.set_theme(self.config.get("theme"), self.system_is_dark(),
                       self.config.get("accent"))
        for window in self.windows:
            window.rebuild()
            window.update()

    def set_accent(self, value):
        self.config.set("accent", value)
        self.apply_theme()

    def pick_accent(self):
        color = QColorDialog.getColor(QColor(core.THEME["primary"]), None,
                                      self.config.t("accent_pick"))
        if color.isValid():
            self.set_accent(color.name())

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
        """Dock the pills to the top edge (or release them back to the anchor)."""
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

    def island_offset(self, window):
        return int(self.config.island_offsets.get(str(window.key()), 0))

    def remember_island(self, window):
        area = window.screen.availableGeometry()
        center = window.x() + window.width() / 2
        offset = int(round(center - (area.x() + area.width() / 2)))
        limit = max(0, (area.width() - window.width()) // 2)
        self.config.island_offsets[str(window.key())] = max(-limit, min(offset, limit))
        self.config.save()
        window.place()

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
        self.config.save()
        for window in self.windows:
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
            window.hide()

    def show_all(self):
        self.hidden = False
        for window in self.windows:
            window.show()
            window.place()

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
