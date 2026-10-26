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

from PySide6.QtCore import (QByteArray, QCoreApplication, QEvent, QObject, QPoint, Qt,
                            QTimer, Signal)
from PySide6.QtGui import (
    QAction, QActionGroup, QColor, QCursor, QFont, QFontMetrics, QGuiApplication,
    QIcon, QPainter, QPainterPath, QPen, QPixmap,
)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QApplication, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QMenu, QWidget)

import vigia_core as core

SIZES = {
    "small": {"font": 9, "icon": 10, "pad_v": 3, "pad_h": 7, "gap": 6},
    "medium": {"font": 10, "icon": 12, "pad_v": 4, "pad_h": 9, "gap": 8},
    "large": {"font": 13, "icon": 15, "pad_v": 6, "pad_h": 12, "gap": 10},
}
SERVER_NAME = "vigia"
MENU_QSS = """
QMenu {
    background-color: #24252b;
    color: #e6e6ec;
    border: 1px solid #3a3b42;
    padding: 4px;
}
QMenu::item { padding: 5px 22px 5px 22px; border-radius: 4px; }
QMenu::item:selected { background-color: #3a3b42; }
QMenu::item:disabled { color: #7c818c; }
QMenu::separator { height: 1px; background: #3a3b42; margin: 4px 6px; }
QMenu::indicator { width: 12px; height: 12px; }
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
    """Keeps the root menu open after a setting changes.

    Submenus close themselves (keep_open=False) so the parent stays visible;
    actions flagged with the "closes_menu" property close the whole popup.
    """

    def __init__(self, keep_open=True, parent=None):
        super().__init__(parent)
        self.keep_open = keep_open

    def _activate(self, action):
        if action is None or not action.isEnabled() or action.menu() is not None:
            return False
        action.trigger()
        if action.property("closes_menu") or not self.keep_open:
            self.hide()
        return True

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
        self.value_labels = []
        self.system_labels = {}
        self.rows = []

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowTitle(core.APP_NAME)
        self.setCursor(Qt.SizeAllCursor)
        self.setMouseTracking(True)

        self.css = SIZES[app.config.get("size")]
        self.box = QHBoxLayout(self)
        self.box.setContentsMargins(self.css["pad_h"], self.css["pad_v"],
                                    max(2, self.css["pad_h"] - 2), self.css["pad_v"])
        self.box.setSpacing(self.css["gap"])
        self.build()
        self.adjustSize()
        self.hover_timer = QTimer(self)
        self.hover_timer.timeout.connect(self.poll_hover)
        self.hover_timer.start(120)
        self.place()

    # -- build ---------------------------------------------------------------
    def clear(self):
        while self.box.count():
            item = self.box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.value_labels = []
        self.system_labels = {}

    def value_label(self, text, tint):
        label = QLabel(text)
        font = QFont(label.font())
        font.setPixelSize(self.css["font"])
        font.setBold(True)
        label.setFont(font)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        metrics = QFontMetrics(font)
        label.setFixedWidth(metrics.horizontalAdvance("100%") + 2)
        label.setStyleSheet(f"color: {tint};")
        label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.value_labels.append(label)
        return label

    def muted_label(self, text):
        label = QLabel(text)
        font = QFont(label.font())
        font.setPixelSize(self.css["font"])
        label.setFont(font)
        label.setStyleSheet("color: rgba(230,230,236,168);")
        label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        return label

    def divider(self):
        line = QWidget()
        line.setFixedSize(1, max(6, self.css["icon"] - 2))
        line.setStyleSheet("background: rgba(255,255,255,41);")
        line.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        return line

    def build(self):
        self.clear()
        style = self.app.config.get("icon_style")
        dpr = self.devicePixelRatioF()

        hidden_providers = self.app.hidden_items("hide_providers")
        rows = [row for row in self.rows
                if row["id"].lower() not in hidden_providers][: self.app.config.get("max_providers")]
        if not rows:
            self.box.addWidget(self.muted_label("—"))
        for row in rows:
            tint = core.icon_tint(row["brand"], style)
            if not row["brand"] or not core.icon_path(row["brand"]):
                initials = QLabel(row["name"][:2].upper())
                font = QFont(initials.font())
                font.setPixelSize(self.css["font"])
                font.setBold(True)
                initials.setFont(font)
                initials.setStyleSheet("color: rgba(230,230,236,168);")
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
            value = self.value_label(row["value"], core.value_tint(
                style, row["percent"], self.app.config.get("alert_warn"),
                self.app.config.get("alert_critical")))
            value.setToolTip(f"{row['name']} — {row['label']}" if row["label"] else row["name"])
            self.box.addWidget(value)

        if self.app.config.get("show_system"):
            hidden_system = self.app.hidden_items("hide_system")
            self.box.addWidget(self.divider())
            for name, reading in self.app.metrics.snapshot():
                if reading is None or name.lower() in hidden_system:
                    continue
                self.box.addWidget(self.muted_label(name))
                value = self.value_label(f"{reading}%", core.value_tint(
                    style, reading, self.app.config.get("alert_warn"),
                    self.app.config.get("alert_critical")))
                self.box.addWidget(value)
                self.system_labels[name] = value

        self.gear = GearLabel(self.show_menu)
        self.gear.setPixmap(gear_pixmap(max(9, self.css["icon"] - 2), dpr))
        self.gear.setFixedSize(max(9, self.css["icon"] - 2), max(9, self.css["icon"] - 2))
        self.gear.setCursor(Qt.PointingHandCursor)
        self.gear.setToolTip(self.app.config.t("gear"))
        self.gear_effect = QGraphicsOpacityEffect(self.gear)
        self.gear_effect.setOpacity(1.0 if self.hovered else 0.0)
        self.gear.setGraphicsEffect(self.gear_effect)
        self.box.addWidget(self.gear)

    # -- paint ---------------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(0, 0, -1, -1)
        radius = rect.height() / 2
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        alpha = self.app.effective_alpha(self.hovered)
        painter.fillPath(path, QColor(20, 20, 24, int(alpha * 255)))
        painter.setPen(QPen(QColor(255, 255, 255, 23), 1))
        painter.drawPath(path)
        painter.end()

    # -- interaction ---------------------------------------------------------
    def show_menu(self):
        # Defer: opening a popup inside the release event makes it close itself.
        QTimer.singleShot(0, lambda: self.app.popup_menu(self.gear))

    def poll_hover(self):
        if self.drag_offset is not None and QGuiApplication.mouseButtons() == Qt.NoButton:
            self.drag_offset = None
            self.drag_started = False
        inside = self.frameGeometry().contains(QCursor.pos())
        if inside != self.hovered:
            self.hovered = inside
            self.gear_effect.setOpacity(1.0 if inside else 0.0)
            self.update()

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
            if not self.drag_started:
                delta = event.globalPosition().toPoint() - self.drag_origin
                if abs(delta.x()) < 3 and abs(delta.y()) < 3:
                    return
                self.drag_started = True
            self.move(event.globalPosition().toPoint() - self.drag_offset)
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
                self.app.remember_position(self)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    # -- placement -----------------------------------------------------------
    def key(self):
        return self.screen.name() or str(self.screen_index)

    def place(self, force=False):
        area = self.screen.availableGeometry()
        stored = None if force else self.app.config.positions.get(self.key())
        if stored:
            x, y = area.x() + stored[0], area.y() + stored[1]
        else:
            x, y = core.anchored_position(
                (area.x(), area.y(), area.width(), area.height()),
                self.width(), self.height(), self.app.config.get("anchor"))
        seams = core.seam_edges(self.screen_index, self.app.screen_geometries())
        x, y = core.clamp_to_area(x, y, self.width(), self.height(),
                                  (area.x(), area.y(), area.width(), area.height()),
                                  core.MARGIN, seams)
        if self.pos() != QPoint(int(x), int(y)):
            self.move(int(x), int(y))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # adjustSize() finishes after the layout runs, so re-anchor here with the
        # real width instead of the previous one.
        if self.drag_offset is None:
            QTimer.singleShot(0, self.place)

    def rebuild(self):
        self.css = SIZES[self.app.config.get("size")]
        self.box.setContentsMargins(self.css["pad_h"], self.css["pad_v"],
                                    max(2, self.css["pad_h"] - 2), self.css["pad_v"])
        self.box.setSpacing(self.css["gap"])
        self.build()
        self.adjustSize()
        self.place()

    def set_rows(self, rows):
        self.rows = rows
        self.build()
        self.adjustSize()
        self.place()

    def update_system(self):
        if not self.system_labels:
            return
        for name, reading in self.app.metrics.snapshot():
            label = self.system_labels.get(name)
            if label is not None and reading is not None:
                label.setText(f"{reading}%")

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
        self.hidden = False
        self.refreshing = False
        self.last_fetch = 0.0
        self.hotkey = None
        self.server = None
        self.data_ready.connect(self.apply_report)

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
        self.rows = core.provider_rows(report, self.config.get("max_providers"))
        self.last_fetch = time.monotonic()
        self.refreshing = False
        for window in self.windows:
            window.set_rows(self.rows)

    def system_tick(self):
        if not self.config.get("show_system"):
            return
        for window in self.windows:
            window.update_system()

    def provider_tick(self):
        if time.monotonic() - self.last_fetch >= self.config.get("refresh_minutes") * 60:
            self.trigger_refresh()

    # -- menu ----------------------------------------------------------------
    def popup_menu(self, anchor=None):
        menu = StickyMenu(keep_open=True, parent=anchor)
        menu.setStyleSheet(MENU_QSS)
        self.menu = menu

        header = menu.addAction(core.APP_NAME)
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

        autostart = QAction(self.config.t("autostart"), menu)
        autostart.setCheckable(True)
        autostart.setChecked(self.config.get("autostart"))
        autostart.toggled.connect(self.set_autostart)
        menu.addAction(autostart)

        hint = menu.addAction(self.config.t("hotkey_hint", accel=self.hotkey.accelerator if self.hotkey else "—"))
        hint.setEnabled(False)

        menu.addSeparator()
        menu.addAction(self.config.t("refresh_now"), self.trigger_refresh)
        menu.addAction(self.config.t("open_config"), self.open_config)
        menu.addAction(self.config.t("reset_position"), self.reset_position)
        hide = menu.addAction(self.config.t("hide"), self.hide_all)
        hide.setProperty("closes_menu", True)
        quit_action = menu.addAction(self.config.t("quit"), self.quit)
        quit_action.setProperty("closes_menu", True)

        menu.exec(QCursor.pos())

    # -- settings ------------------------------------------------------------
    def set_opacity(self, value):
        self.config.set("opacity", value / 100.0)
        for window in self.windows:
            window.update()

    def set_size(self, value):
        self.config.set("size", value)
        for window in self.windows:
            window.rebuild()

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

    def set_language(self, value):
        self.config.set("language", value)
        for window in self.windows:
            window.rebuild()

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
        sub = StickyMenu(keep_open=False, parent=parent)
        sub.setTitle(title)
        sub.setStyleSheet(MENU_QSS)
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
