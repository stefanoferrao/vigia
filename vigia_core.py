"""VigIA core — data, config, translations and metrics, with no GUI toolkit.

Both shells (GTK on Linux, Qt on Windows) import this module so that behaviour
and wording stay identical. Everything here is plain Python 3.11+.
"""

import glob
import json
import os
import platform
import re
import shutil
import hashlib
import io
import subprocess
import tarfile
import tempfile
import tomllib
import urllib.parse
import urllib.request
from datetime import datetime

APP_NAME = "VigIA"
VERSION = "2.5.5"
IS_WINDOWS = platform.system() == "Windows"
HOME = os.path.expanduser("~")
MARGIN = 18

if IS_WINDOWS:
    CONFIG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.join(HOME, "AppData", "Roaming"), "vigia")
    CACHE_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.join(HOME, "AppData", "Local"), "vigia")
    RUNTIME_DIR = CACHE_DIR
else:
    CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.join(HOME, ".config"), "vigia")
    CACHE_DIR = os.path.join(HOME, ".cache", "vigia")
    RUNTIME_DIR = os.environ.get("XDG_RUNTIME_DIR") or os.path.join(HOME, ".cache")

CONFIG_PATH = os.path.join(CONFIG_DIR, "vigia.toml")
LEGACY_CONFIG = os.path.join(HOME, ".config", "ai-usagebar", "overlay.toml")
LOG_PATH = os.path.join(CACHE_DIR, "vigia.log")
AUTOSTART_PATH = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.join(HOME, ".config"),
    "autostart", "vigia.desktop",
)
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "VigIA"

LANGUAGES = {
    "pt": "Português (Brasil)",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
}

STRINGS = {
    "pt": {
        "menu_opacity": "Transparência",
        "menu_size": "Tamanho",
        "menu_icons": "Ícones",
        "menu_bars": "Barras de progresso",
        "menu_pulse": "Pulsar em estado crítico",
        "accent_pick": "Cor de realce…",
        "accent_reset": "Restaurar cor de realce",
        "menu_theme": "Tema",
        "theme_auto": "Automático (sistema)",
        "menu_monitor": "Monitor",
        "menu_anchor": "Posição",
        "menu_language": "Idioma",
        "menu_items": "Itens",
        "menu_metric": "O que vigiar",
        "metric_auto": "Maior uso (automático)",
        "metric_waiting": "Aguardando dados…",
        "menu_island": "Modo ilha (encaixar na borda)",
        "size_small": "Pequeno", "size_medium": "Médio", "size_large": "Grande",
        "icons_brand": "Cor da marca", "icons_mono": "Monocromático",
        "icons_alert": "Alerta por uso",
        "monitor_primary": "Principal", "monitor_secondary": "Secundário",
        "monitor_all": "Ambos", "monitor_screen": "Tela {n}",
        "always_on_top": "Sempre no topo",
        "show_system": "Mostrar CPU / RAM / GPU",
        "autostart": "Iniciar com a sessão",
        "hotkey_hint": "Atalho: {accel}",
        "refresh_now": "Atualizar agora",
        "open_config": "Abrir config.toml",
        "reset_position": "Restaurar posição",
        "hide": "Esconder",
        "quit": "Sair",
        "gear": "Configurações",
        "language_auto": "Automático (sistema)",
        "anchor_top_left": "Topo esquerdo", "anchor_top_center": "Topo centro",
        "anchor_top_right": "Topo direito", "anchor_middle_left": "Meio esquerdo",
        "anchor_middle_center": "Meio centro", "anchor_middle_right": "Meio direito",
        "anchor_bottom_left": "Base esquerda", "anchor_bottom_center": "Base centro",
        "anchor_bottom_right": "Base direita",
        "menu_island_position": "Posição da ilha",
        "menu_source_update": "Atualizar fonte de dados (ai-usagebar {version})",
        "island_top": "Topo",
        "island_bottom": "Base",
        "island_left": "Esquerda",
        "island_right": "Direita",
        "along_left": "esquerda",
        "along_center": "centro",
        "along_right": "direita",
        "along_top": "topo",
        "along_middle": "meio",
        "along_bottom": "base",
    },
    "en": {
        "menu_opacity": "Opacity",
        "menu_size": "Size",
        "menu_icons": "Icons",
        "menu_bars": "Progress bars",
        "menu_pulse": "Pulse when critical",
        "accent_pick": "Accent color…",
        "accent_reset": "Reset accent color",
        "menu_theme": "Theme",
        "theme_auto": "Automatic (system)",
        "menu_monitor": "Monitor",
        "menu_anchor": "Position",
        "menu_language": "Language",
        "menu_items": "Items",
        "menu_metric": "What to watch",
        "metric_auto": "Most used (auto)",
        "metric_waiting": "Waiting for data…",
        "menu_island": "Island mode (dock to an edge)",
        "size_small": "Small", "size_medium": "Medium", "size_large": "Large",
        "icons_brand": "Brand colour", "icons_mono": "Monochrome",
        "icons_alert": "Usage alert",
        "monitor_primary": "Primary", "monitor_secondary": "Secondary",
        "monitor_all": "Both", "monitor_screen": "Screen {n}",
        "always_on_top": "Always on top",
        "show_system": "Show CPU / RAM / GPU",
        "autostart": "Start with session",
        "hotkey_hint": "Shortcut: {accel}",
        "refresh_now": "Refresh now",
        "open_config": "Open config.toml",
        "reset_position": "Reset position",
        "hide": "Hide",
        "quit": "Quit",
        "gear": "Settings",
        "language_auto": "Automatic (system)",
        "anchor_top_left": "Top left", "anchor_top_center": "Top centre",
        "anchor_top_right": "Top right", "anchor_middle_left": "Middle left",
        "anchor_middle_center": "Middle centre", "anchor_middle_right": "Middle right",
        "anchor_bottom_left": "Bottom left", "anchor_bottom_center": "Bottom centre",
        "anchor_bottom_right": "Bottom right",
        "menu_island_position": "Island position",
        "menu_source_update": "Update data source (ai-usagebar {version})",
        "island_top": "Top",
        "island_bottom": "Bottom",
        "island_left": "Left",
        "island_right": "Right",
        "along_left": "left",
        "along_center": "centre",
        "along_right": "right",
        "along_top": "top",
        "along_middle": "middle",
        "along_bottom": "bottom",
    },
    "es": {
        "menu_opacity": "Opacidad",
        "menu_size": "Tamaño",
        "menu_icons": "Iconos",
        "menu_bars": "Barras de progreso",
        "menu_pulse": "Pulsar en estado crítico",
        "accent_pick": "Color de acento…",
        "accent_reset": "Restaurar color de acento",
        "menu_theme": "Tema",
        "theme_auto": "Automático (sistema)",
        "menu_monitor": "Monitor",
        "menu_anchor": "Posición",
        "menu_language": "Idioma",
        "menu_items": "Elementos",
        "menu_metric": "Qué vigilar",
        "metric_auto": "Mayor uso (automático)",
        "metric_waiting": "Esperando datos…",
        "menu_island": "Modo isla (anclar a un borde)",
        "size_small": "Pequeño", "size_medium": "Mediano", "size_large": "Grande",
        "icons_brand": "Color de marca", "icons_mono": "Monocromático",
        "icons_alert": "Alerta por uso",
        "monitor_primary": "Principal", "monitor_secondary": "Secundario",
        "monitor_all": "Ambos", "monitor_screen": "Pantalla {n}",
        "always_on_top": "Siempre encima",
        "show_system": "Mostrar CPU / RAM / GPU",
        "autostart": "Iniciar con la sesión",
        "hotkey_hint": "Atajo: {accel}",
        "refresh_now": "Actualizar ahora",
        "open_config": "Abrir config.toml",
        "reset_position": "Restaurar posición",
        "hide": "Ocultar",
        "quit": "Salir",
        "gear": "Ajustes",
        "language_auto": "Automático (sistema)",
        "anchor_top_left": "Arriba izquierda", "anchor_top_center": "Arriba centro",
        "anchor_top_right": "Arriba derecha", "anchor_middle_left": "Medio izquierda",
        "anchor_middle_center": "Medio centro", "anchor_middle_right": "Medio derecha",
        "anchor_bottom_left": "Abajo izquierda", "anchor_bottom_center": "Abajo centro",
        "anchor_bottom_right": "Abajo derecha",
        "menu_island_position": "Posición de la isla",
        "menu_source_update": "Actualizar fuente de datos (ai-usagebar {version})",
        "island_top": "Arriba",
        "island_bottom": "Abajo",
        "island_left": "Izquierda",
        "island_right": "Derecha",
        "along_left": "izquierda",
        "along_center": "centro",
        "along_right": "derecha",
        "along_top": "arriba",
        "along_middle": "medio",
        "along_bottom": "abajo",
    },
    "fr": {
        "menu_opacity": "Opacité",
        "menu_size": "Taille",
        "menu_icons": "Icônes",
        "menu_bars": "Barres de progression",
        "menu_pulse": "Pulser en état critique",
        "accent_pick": "Couleur d'accent…",
        "accent_reset": "Réinitialiser la couleur d'accent",
        "menu_theme": "Thème",
        "theme_auto": "Automatique (système)",
        "menu_monitor": "Écran",
        "menu_anchor": "Position",
        "menu_language": "Langue",
        "menu_items": "Éléments",
        "menu_metric": "Quoi surveiller",
        "metric_auto": "Le plus utilisé (auto)",
        "metric_waiting": "En attente des données…",
        "menu_island": "Mode île (ancrer à un bord)",
        "size_small": "Petit", "size_medium": "Moyen", "size_large": "Grand",
        "icons_brand": "Couleur de marque", "icons_mono": "Monochrome",
        "icons_alert": "Alerte d'usage",
        "monitor_primary": "Principal", "monitor_secondary": "Secondaire",
        "monitor_all": "Les deux", "monitor_screen": "Écran {n}",
        "always_on_top": "Toujours au-dessus",
        "show_system": "Afficher CPU / RAM / GPU",
        "autostart": "Lancer à la connexion",
        "hotkey_hint": "Raccourci : {accel}",
        "refresh_now": "Actualiser",
        "open_config": "Ouvrir config.toml",
        "reset_position": "Réinitialiser la position",
        "hide": "Masquer",
        "quit": "Quitter",
        "gear": "Réglages",
        "language_auto": "Automatique (système)",
        "anchor_top_left": "Haut gauche", "anchor_top_center": "Haut centre",
        "anchor_top_right": "Haut droite", "anchor_middle_left": "Milieu gauche",
        "anchor_middle_center": "Milieu centre", "anchor_middle_right": "Milieu droite",
        "anchor_bottom_left": "Bas gauche", "anchor_bottom_center": "Bas centre",
        "anchor_bottom_right": "Bas droite",
        "menu_island_position": "Position de l'île",
        "menu_source_update": "Mettre à jour la source de données (ai-usagebar {version})",
        "island_top": "Haut",
        "island_bottom": "Bas",
        "island_left": "Gauche",
        "island_right": "Droite",
        "along_left": "gauche",
        "along_center": "centre",
        "along_right": "droite",
        "along_top": "haut",
        "along_middle": "milieu",
        "along_bottom": "bas",
    },
    "de": {
        "menu_opacity": "Deckkraft",
        "menu_size": "Größe",
        "menu_icons": "Symbole",
        "menu_bars": "Fortschrittsbalken",
        "menu_pulse": "Pulsieren bei kritischem Wert",
        "accent_pick": "Akzentfarbe…",
        "accent_reset": "Akzentfarbe zurücksetzen",
        "menu_theme": "Design",
        "theme_auto": "Automatisch (System)",
        "menu_monitor": "Monitor",
        "menu_anchor": "Position",
        "menu_language": "Sprache",
        "menu_items": "Elemente",
        "menu_metric": "Was überwachen",
        "metric_auto": "Höchste Nutzung (automatisch)",
        "metric_waiting": "Warte auf Daten…",
        "menu_island": "Inselmodus (an einer Kante andocken)",
        "size_small": "Klein", "size_medium": "Mittel", "size_large": "Groß",
        "icons_brand": "Markenfarbe", "icons_mono": "Einfarbig",
        "icons_alert": "Nutzungswarnung",
        "monitor_primary": "Primär", "monitor_secondary": "Sekundär",
        "monitor_all": "Beide", "monitor_screen": "Bildschirm {n}",
        "always_on_top": "Immer im Vordergrund",
        "show_system": "CPU / RAM / GPU anzeigen",
        "autostart": "Mit Sitzung starten",
        "hotkey_hint": "Tastenkürzel: {accel}",
        "refresh_now": "Jetzt aktualisieren",
        "open_config": "config.toml öffnen",
        "reset_position": "Position zurücksetzen",
        "hide": "Ausblenden",
        "quit": "Beenden",
        "gear": "Einstellungen",
        "language_auto": "Automatisch (System)",
        "anchor_top_left": "Oben links", "anchor_top_center": "Oben Mitte",
        "anchor_top_right": "Oben rechts", "anchor_middle_left": "Mitte links",
        "anchor_middle_center": "Mitte", "anchor_middle_right": "Mitte rechts",
        "anchor_bottom_left": "Unten links", "anchor_bottom_center": "Unten Mitte",
        "anchor_bottom_right": "Unten rechts",
        "menu_island_position": "Position der Insel",
        "menu_source_update": "Datenquelle aktualisieren (ai-usagebar {version})",
        "island_top": "Oben",
        "island_bottom": "Unten",
        "island_left": "Links",
        "island_right": "Rechts",
        "along_left": "links",
        "along_center": "Mitte",
        "along_right": "rechts",
        "along_top": "oben",
        "along_middle": "Mitte",
        "along_bottom": "unten",
    },
}

ANCHORS = {
    "top-left": "anchor_top_left", "top-center": "anchor_top_center",
    "top-right": "anchor_top_right", "middle-left": "anchor_middle_left",
    "middle-center": "anchor_middle_center", "middle-right": "anchor_middle_right",
    "bottom-left": "anchor_bottom_left", "bottom-center": "anchor_bottom_center",
    "bottom-right": "anchor_bottom_right",
}

DEFAULTS = {
    "opacity": 0.82,
    "size": "medium",
    "icon_style": "brand",       # brand | mono | alert
    "monitor": "primary",        # primary | secondary | all | <index> | <screen name>
    "anchor": "top-right",
    "island": False,         # dock the pills to a screen edge, Dynamic Island style
    "island_anchor": "top-center",  # edge-position: top|bottom-left|center|right, left|right-top|middle|bottom
    "always_on_top": True,
    "show_system": False,
    "autostart": True,
    "refresh_minutes": 5,
    "max_providers": 4,
    "hotkey": "<Control><Alt>v",
    "language": "auto",
    "theme": "vigia",            # vigia | auto | any file stem in themes/ (DESIGN.md tokens)
    "accent": "",                # "#rrggbb" overrides the theme's primary colour
    "bars": True,                # thin usage bar under each number
    "pulse": True,               # icon_style = "alert": critical values breathe
    "alert_warn": 60,        # icon_style = "alert": amber from this percentage
    "alert_critical": 80,    # ... and red from this one
    "hide_providers": "",    # comma-separated provider ids to keep out of the pill
    "hide_system": "",       # comma-separated cpu,ram,gpu to keep out of the pill
}
ORDER = list(DEFAULTS)


def log(message):
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}\n")
    except OSError:
        pass


def locale_code(value):
    """"pt_BR.UTF-8" -> "pt"; a colon list ("pt_BR:pt:en") yields its first known language."""
    for part in str(value or "").split(":"):
        code = part.split("_", 1)[0].split(".", 1)[0].split("@", 1)[0].strip().lower()
        if code in STRINGS:
            return code
    return None


def locale_file_language():
    """Session files that name the system language when the process env carries none."""
    for path in (os.path.join(HOME, ".config", "locale.conf"), "/etc/locale.conf",
                 "/etc/default/locale"):
        try:
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    name, _, value = line.strip().partition("=")
                    if name in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
                        code = locale_code(value.strip("\"'"))
                        if code:
                            return code
        except OSError:
            continue
    return None


def system_language():
    for name in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        code = locale_code(os.environ.get(name))
        if code:
            return code
    if not IS_WINDOWS:
        code = locale_file_language()
        if code:
            return code
    if IS_WINDOWS:
        try:
            import ctypes
            code = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
            primary = {9: "en", 7: "de", 10: "es", 12: "fr", 16: "pt", 22: "pt"}
            if code in primary:
                return primary[code]
        except Exception:
            pass
    return "en"


def translate(language, key, **kwargs):
    text = STRINGS.get(language, STRINGS["en"]).get(key) or STRINGS["en"].get(key, key)
    return text.format(**kwargs) if kwargs else text


# --------------------------------------------------------------------------- config

def _toml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, int):
        return str(value)
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


class Config:
    def __init__(self, path=None):
        self.path = path or CONFIG_PATH
        self.values = dict(DEFAULTS)
        self.positions = {}
        self.metrics = {}
        self.island_offsets = {}
        self.load()

    def load(self):
        self.positions = {}
        self.metrics = {}
        self.island_offsets = {}
        if not os.path.isfile(self.path) and os.path.isfile(LEGACY_CONFIG):
            try:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                shutil.copyfile(LEGACY_CONFIG, self.path)
                log(f"migrated config from {LEGACY_CONFIG}")
            except OSError as error:
                log(f"config migration failed: {error}")
        try:
            with open(self.path, "rb") as handle:
                raw = tomllib.load(handle).get("overlay", {})
        except (OSError, tomllib.TOMLDecodeError):
            raw = {}
        for key, default in DEFAULTS.items():
            value = raw.get(key, default)
            try:
                if isinstance(default, bool):
                    self.values[key] = bool(value)
                elif isinstance(default, float):
                    self.values[key] = float(value)
                elif isinstance(default, int):
                    self.values[key] = int(value)
                else:
                    self.values[key] = str(value)
            except (TypeError, ValueError):
                self.values[key] = default
        positions = raw.get("positions") or {}
        if isinstance(positions, dict):
            for key, value in positions.items():
                try:
                    x, y = value
                    self.positions[str(key)] = (int(x), int(y))
                except (TypeError, ValueError):
                    continue
        choices = raw.get("metrics") or {}
        if isinstance(choices, dict):
            for key, value in choices.items():
                choice = str(value or "").strip()
                if key and choice:
                    self.metrics[str(key).lower()] = choice
        offsets = raw.get("island_offsets") or {}
        if isinstance(offsets, dict):
            for key, value in offsets.items():
                try:
                    self.island_offsets[str(key)] = int(value)
                except (TypeError, ValueError):
                    continue
        self.sanitize()
        if not os.path.isfile(self.path):
            self.save()

    def sanitize(self):
        self.values["opacity"] = min(1.0, max(0.40, self.values["opacity"]))
        if self.values["size"] not in ("small", "medium", "large"):
            self.values["size"] = DEFAULTS["size"]
        if self.values["icon_style"] not in ("brand", "mono", "alert"):
            self.values["icon_style"] = DEFAULTS["icon_style"]
        # "primary" / "secondary" / "all" or a screen name (also legacy indexes)
        if not str(self.values["monitor"]).strip():
            self.values["monitor"] = DEFAULTS["monitor"]
        if self.values["island_anchor"] not in ISLAND_ANCHORS:
            self.values["island_anchor"] = DEFAULTS["island_anchor"]
        if self.values["anchor"] not in ANCHORS:
            self.values["anchor"] = DEFAULTS["anchor"]
        if not str(self.values["theme"]).strip():
            self.values["theme"] = DEFAULTS["theme"]
        if not re.match(r"^#[0-9a-fA-F]{6}$", self.values["accent"]):
            self.values["accent"] = ""
        if self.values["language"] not in STRINGS and self.values["language"] != "auto":
            self.values["language"] = DEFAULTS["language"]
        self.values["refresh_minutes"] = max(1, min(60, self.values["refresh_minutes"]))
        self.values["max_providers"] = max(1, min(8, self.values["max_providers"]))
        self.values["alert_warn"] = max(1, min(99, self.values["alert_warn"]))
        self.values["alert_critical"] = max(self.values["alert_warn"] + 1,
                                            min(100, self.values["alert_critical"]))
        for key in ("hide_providers", "hide_system"):
            items = [item.strip().lower() for item in str(self.values[key]).split(",")]
            self.values[key] = ",".join(dict.fromkeys(item for item in items if item))

    def save(self):
        self.sanitize()
        lines = [
            "# VigIA — edits here are picked up by `vigia --reload`.",
            "[overlay]",
        ]
        for key in ORDER:
            lines.append(f"{key} = {_toml_value(self.values[key])}")
        if self.positions:
            lines.append("")
            lines.append("[overlay.positions]")
            for key in sorted(self.positions):
                x, y = self.positions[key]
                lines.append(f'"{key}" = [{int(x)}, {int(y)}]')
        if self.metrics:
            lines.append("")
            lines.append("[overlay.metrics]")
            for key in sorted(self.metrics):
                lines.append(f'"{key}" = {_toml_value(self.metrics[key])}')
        if self.island_offsets:
            lines.append("")
            lines.append("[overlay.island_offsets]")
            for key in sorted(self.island_offsets):
                lines.append(f'"{key}" = {int(self.island_offsets[key])}')
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines) + "\n")
        except OSError as error:
            log(f"config write failed: {error}")

    def set(self, key, value):
        self.values[key] = value
        self.save()

    def metric_choice(self, provider_id):
        """Which metric of a provider to show: "auto" or a reported label."""
        return self.metrics.get(str(provider_id).lower(), "auto")

    def set_metric(self, provider_id, choice):
        key = str(provider_id).lower()
        if choice and str(choice).strip().lower() != "auto":
            self.metrics[key] = str(choice).strip()
        else:
            self.metrics.pop(key, None)
        self.save()

    def get(self, key):
        return self.values[key]

    def language(self):
        choice = self.get("language")
        return choice if choice in STRINGS else system_language()

    def t(self, key, **kwargs):
        return translate(self.language(), key, **kwargs)


def set_autostart(enabled, command):
    """Register (or remove) the app at login. `command` is the full CLI line."""
    if IS_WINDOWS:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                if enabled:
                    winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, command)
                else:
                    try:
                        winreg.DeleteValue(key, RUN_VALUE)
                    except FileNotFoundError:
                        pass
        except OSError as error:
            log(f"autostart update failed: {error}")
        return

    if enabled:
        try:
            os.makedirs(os.path.dirname(AUTOSTART_PATH), exist_ok=True)
            with open(AUTOSTART_PATH, "w", encoding="utf-8") as handle:
                handle.write(
                    "[Desktop Entry]\n"
                    "Type=Application\n"
                    "Name=VigIA\n"
                    "Comment=AI usage and system metrics at a glance\n"
                    f"Exec={command}\n"
                    "Icon=vigia\n"
                    "Terminal=false\n"
                    "X-GNOME-Autostart-enabled=true\n"
                    "X-GNOME-Autostart-Delay=6\n"
                )
        except OSError as error:
            log(f"autostart write failed: {error}")
    else:
        try:
            os.unlink(AUTOSTART_PATH)
        except FileNotFoundError:
            pass
        except OSError as error:
            log(f"autostart remove failed: {error}")


# ------------------------------------------------------------------------ providers

USAGEBAR_REPO = "akitaonrails/ai-usagebar"
USAGEBAR_BIN = "ai-usagebar"
DOWNLOAD_LIMIT = 80 * 1024 * 1024     # the biggest release asset is ~17 MB; refuse anything absurd
TRUSTED_HOSTS = ("github.com", "githubusercontent.com")


def bundled_dir(home=None):
    """Where VigIA keeps its own copy of the ai-usagebar data source."""
    home = home or HOME
    if IS_WINDOWS:
        local = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
        return os.path.join(local, "vigia", "bin")
    return os.path.join(home, ".local", "share", "vigia", "bin")


def usagebar_asset(system=None, machine=None):
    """Release asset for this platform: (asset name, "tar" | "exe"), or None if unsupported."""
    system = (system or platform.system()).lower()
    machine = (machine or platform.machine()).lower()
    arch = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"}.get(machine)
    if system == "linux" and arch:
        return f"ai-usagebar-linux-{arch}.tar.gz", "tar"
    if system == "windows" and arch == "x86_64":
        return "ai-usagebar-windows-x86_64.exe", "exe"
    return None


def parse_sha256(text):
    """First 64-hex token of a `sha256sum`-style file."""
    match = re.search(r"\b([0-9a-fA-F]{64})\b", text or "")
    return match.group(1).lower() if match else None


def _download(url, timeout=60):
    """GET over https from GitHub only (also after redirects), capped in size."""
    if not url.startswith("https://"):
        raise ValueError("só https")
    request = urllib.request.Request(url, headers={"User-Agent": f"VigIA/{VERSION}"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        host = urllib.parse.urlparse(response.geturl()).hostname or ""
        if not any(host == ok or host.endswith("." + ok) for ok in TRUSTED_HOSTS):
            raise ValueError(f"host inesperado: {host}")
        data = response.read(DOWNLOAD_LIMIT + 1)
    if len(data) > DOWNLOAD_LIMIT:
        raise ValueError("download grande demais")
    return data


def extract_usagebar(blob, kind):
    """The ai-usagebar executable bytes out of a release asset (tar.gz member or raw .exe)."""
    if kind == "exe":
        return blob
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as archive:
        for member in archive.getmembers():
            if os.path.basename(member.name) == USAGEBAR_BIN and member.isfile():
                return archive.extractfile(member).read()
    raise ValueError("binário não encontrado no pacote")


def usagebar_version(binary):
    """Version string of an ai-usagebar executable ("1.47.0"), or "" if it will not tell."""
    try:
        options = {"capture_output": True, "text": True, "timeout": 10}
        if IS_WINDOWS:
            options["creationflags"] = 0x08000000
        out = subprocess.run([binary, "--version"], **options).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    match = re.search(r"(\d+\.\d+\.\d+)", out or "")
    return match.group(1) if match else ""


def latest_usagebar_version():
    try:
        data = _download(f"https://api.github.com/repos/{USAGEBAR_REPO}/releases/latest", timeout=20)
        return str(json.loads(data).get("tag_name", "")).lstrip("v")
    except (OSError, ValueError):
        return ""


def ensure_usagebar(force=False, fetch=_download):
    """Make sure VigIA owns a working ai-usagebar; download and verify it when it does not.

    Returns the executable path, or None if this platform has no release or the download
    failed (the caller falls back to whatever is on the system). The asset is checked
    against the sha256 published beside it before anything is written."""
    target = os.path.join(bundled_dir(), USAGEBAR_BIN + (".exe" if IS_WINDOWS else ""))
    if os.path.isfile(target) and not force:
        return target
    asset = usagebar_asset()
    if asset is None:
        return None
    name, kind = asset
    base = f"https://github.com/{USAGEBAR_REPO}/releases/latest/download/{name}"
    try:
        blob = fetch(base)
        expected = parse_sha256(fetch(base + ".sha256").decode("utf-8", "replace"))
        if not expected or hashlib.sha256(blob).hexdigest() != expected:
            raise ValueError("sha256 não confere")
        binary = extract_usagebar(blob, kind)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=os.path.dirname(target), prefix=".ua-")
        with os.fdopen(handle, "wb") as out:
            out.write(binary)
        os.chmod(temp, 0o755)
        os.replace(temp, target)
        log(f"ai-usagebar installed at {target}")
        return target
    except (OSError, ValueError, tarfile.TarError) as error:
        log(f"ai-usagebar download failed: {error}")
        return None


def installed_binary(name, home=None, override=None):
    """Find the ai-usagebar CLI without trusting an arbitrary PATH entry."""
    home = home or HOME
    if override:
        return override
    candidates = [
        os.path.join(bundled_dir(home), name + (".exe" if IS_WINDOWS else "")),  # VigIA's own copy first
        os.path.join(home, ".local", "bin", name),
        os.path.join(home, ".cargo", "bin", name),
        "/usr/local/bin/" + name,
        "/usr/bin/" + name,
    ]
    if IS_WINDOWS:
        local = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
        candidates = [
            candidates[0],
            os.path.join(local, "Programs", "ai-usagebar", name + ".exe"),
            os.path.join(local, "Programs", name, name + ".exe"),
            os.path.join(local, name, name + ".exe"),
        ]
    for candidate in candidates:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    found = shutil.which(name) or (shutil.which(name + ".exe") if IS_WINDOWS else None)
    return found or (candidates[0] if candidates else name)


def metric_display(metric):
    percent = metric.get("percent")
    if metric.get("headline") == "value" and metric.get("value") not in (None, ""):
        return str(metric["value"])
    if isinstance(percent, (int, float)):
        return f"{percent:g}%"
    return str(metric.get("value") or "—")


def quota_metrics(entry):
    """Metrics that describe a quota window, in report order."""
    metrics = entry.get("metrics") or []
    return [metric for metric in metrics if not metric.get("group")] or list(metrics)


def metric_slug(value):
    """Label as lowercase letters/digits, so "Weekly (7d)" == "weekly 7d"."""
    text = value.get("label") if isinstance(value, dict) else value
    return "".join(char for char in str(text or "").lower() if char.isalnum())


def matching_metric(entry, choice):
    """The reported metric whose label matches `choice`; None when it is gone."""
    wanted = metric_slug(choice)
    if not wanted:
        return None
    for metric in quota_metrics(entry):
        if metric_slug(metric) == wanted:
            return metric
    return None


def pick_metric(entry, choice="auto"):
    """Metric shown for a provider: the chosen label, else the most consumed one."""
    metrics = quota_metrics(entry)
    if not metrics:
        return None
    if str(choice or "").strip().lower() != "auto":
        chosen = matching_metric(entry, choice)
        if chosen is not None:
            return chosen
    return max(metrics, key=lambda item: item.get("percent") or 0)


def summary_metric(entry):
    return pick_metric(entry)


def dashboard_entries(data):
    data = data or {}
    entries = list(data.get("entries") or [])
    order = data.get("overview_vendors")
    if isinstance(order, list) and order:
        rank = {}
        for item in order:
            if isinstance(item, str) and item and item not in rank:
                rank[item] = len(rank)

        def vendor(entry):
            slug = str(entry.get("id") or "").split("@", 1)[0]
            return slug or str(entry.get("name") or "")

        indexed = list(enumerate(entries))
        indexed.sort(key=lambda pair: (rank.get(vendor(pair[1]), len(rank)), pair[0]))
        return [entry for _, entry in indexed]
    primary = data.get("primary")
    entries.sort(key=lambda entry: (entry.get("id") != primary and entry.get("name") != primary))
    return entries


def fetch_report(binary=None, timeout=25):
    binary = binary or installed_binary("ai-usagebar", override=os.environ.get("AI_USAGEBAR_BIN"))
    if not os.path.isfile(binary):  # nothing on the system: fetch VigIA's own copy once
        binary = ensure_usagebar() or binary
    options = {"capture_output": True, "text": True, "timeout": timeout}
    if IS_WINDOWS:
        options["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    result = subprocess.run([binary, "usage", "--json"], **options)
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError((result.stderr or "").strip()[:200] or f"ai-usagebar rc={result.returncode}")
    return json.loads(result.stdout)


def provider_rows(report, limit=4, choices=None):
    """One row per provider, showing the metric each provider is set to."""
    choices = choices or {}
    rows = []
    for entry in dashboard_entries(report):
        provider_id = str(entry.get("id") or entry.get("brand") or "")
        metric = pick_metric(entry, choices.get(provider_id.lower(), "auto"))
        if metric is None:
            continue
        brand = str(entry.get("brand") or entry.get("id") or "").split("@", 1)[0]
        rows.append({
            "id": provider_id or brand,
            "brand": brand,
            "name": str(entry.get("display_name") or entry.get("name") or brand),
            "value": metric_display(metric),
            "percent": metric.get("percent"),
            "label": metric.get("label") or "",
        })
        if len(rows) >= limit:
            break
    return rows


# ------------------------------------------------------------------------- metrics

class SystemMetrics:
    """CPU/RAM/GPU. psutil when present; /proc and sysfs on Linux; nvidia-smi on Windows."""

    def __init__(self):
        try:
            import psutil
            self._psutil = psutil
            psutil.cpu_percent(None)
        except ImportError:
            self._psutil = None
        self._last_cpu = None if self._psutil else self._cpu_sample()

    @staticmethod
    def _cpu_sample():
        try:
            with open("/proc/stat", encoding="ascii") as handle:
                fields = handle.readline().split()[1:]
            values = [int(value) for value in fields]
        except (OSError, ValueError, IndexError):
            return None
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        return (sum(values), idle)

    def cpu(self):
        if self._psutil is not None:
            try:
                return max(0, min(100, round(self._psutil.cpu_percent(None))))
            except Exception:
                return None
        if IS_WINDOWS:
            return None
        sample = self._cpu_sample()
        if not sample or not self._last_cpu:
            self._last_cpu = sample
            return None
        total = sample[0] - self._last_cpu[0]
        idle = sample[1] - self._last_cpu[1]
        self._last_cpu = sample
        if total <= 0:
            return None
        return max(0, min(100, round((total - idle) * 100 / total)))

    def ram(self):
        if self._psutil is not None:
            try:
                return max(0, min(100, round(self._psutil.virtual_memory().percent)))
            except Exception:
                return None
        if IS_WINDOWS:
            return None
        try:
            values = {}
            with open("/proc/meminfo", encoding="ascii") as handle:
                for line in handle:
                    key, _, rest = line.partition(":")
                    values[key] = int(rest.split()[0])
            total = values.get("MemTotal", 0)
            available = values.get("MemAvailable", values.get("MemFree", 0))
        except (OSError, ValueError, IndexError):
            return None
        if total <= 0:
            return None
        return max(0, min(100, round((total - available) * 100 / total)))

    def gpu(self):
        if IS_WINDOWS:
            return self._gpu_nvidia()
        for path in sorted(glob.glob("/sys/class/drm/card*/device/gpu_busy_percent")):
            try:
                with open(path, encoding="ascii") as handle:
                    return max(0, min(100, int(handle.read().strip())))
            except (OSError, ValueError):
                continue
        return self._gpu_nvidia()

    @staticmethod
    def _gpu_nvidia():
        if not shutil.which("nvidia-smi"):
            return None
        try:
            options = {"capture_output": True, "text": True, "timeout": 4}
            if IS_WINDOWS:
                options["creationflags"] = 0x08000000
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                **options,
            )
            first = result.stdout.strip().splitlines()[0]
            return max(0, min(100, int(first.strip())))
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            return None

    def snapshot(self):
        return [("CPU", self.cpu()), ("RAM", self.ram()), ("GPU", self.gpu())]


# ------------------------------------------------------------------------ geometry

def anchored_position(area, width, height, anchor, margin=MARGIN):
    """Top-left corner for a box of `width`x`height` inside (x, y, w, h)."""
    x0, y0, area_w, area_h = area
    vertical, horizontal = anchor.split("-", 1)
    x = {
        "left": x0 + margin,
        "center": x0 + (area_w - width) // 2,
        "right": x0 + area_w - width - margin,
    }[horizontal]
    y = {
        "top": y0 + margin,
        "middle": y0 + (area_h - height) // 2,
        "bottom": y0 + area_h - height - margin,
    }[vertical]
    return x, y


ISLAND_ANCHORS = [f"{edge}-{along}" for edge, alongs in (
    ("top", ("left", "center", "right")), ("bottom", ("left", "center", "right")),
    ("left", ("top", "middle", "bottom")), ("right", ("top", "middle", "bottom")))
    for along in alongs]


def island_edge(anchor):
    return str(anchor).split("-", 1)[0]


def island_position(area, anchor, width, height, offset=0):
    """Top-left corner of an island docked to an edge of `area`.

    `anchor` is "<edge>-<where along it>"; `offset` nudges the island along the edge
    (x for top/bottom, y for left/right) and is clamped so it never leaves the area."""
    x0, y0, area_w, area_h = area
    edge, along = str(anchor).split("-", 1)
    if edge in ("top", "bottom"):
        base = {"left": x0, "center": x0 + (area_w - width) / 2,
                "right": x0 + area_w - width}.get(along, x0 + (area_w - width) / 2)
        x = max(x0, min(base + offset, x0 + area_w - width))
        y = y0 if edge == "top" else y0 + area_h - height
    else:
        base = {"top": y0, "middle": y0 + (area_h - height) / 2,
                "bottom": y0 + area_h - height}.get(along, y0 + (area_h - height) / 2)
        y = max(y0, min(base + offset, y0 + area_h - height))
        x = x0 if edge == "left" else x0 + area_w - width
    return int(round(x)), int(round(y))


def island_x(area, width, offset=0):
    """Left edge of a top-centred island, nudged by the saved horizontal offset."""
    x0, _y0, area_w, _area_h = area
    x = x0 + (area_w - width) / 2 + offset
    x = max(x0, min(x, x0 + area_w - width))
    return int(round(x))


def clamp_to_area(x, y, width, height, area, margin=MARGIN, seams=(False, False, False, False)):
    """Keep a box inside an area; shared edges get `margin`, outer ones may be flush."""
    x0, y0, area_w, area_h = area
    left, right, top, bottom = seams
    min_x = x0 + (margin if left else 0)
    max_x = x0 + area_w - width - (margin if right else 0)
    if max_x < min_x:
        min_x, max_x = x0, x0 + area_w - width
    min_y = y0 + (margin if top else 0)
    max_y = y0 + area_h - height - (margin if bottom else 0)
    if max_y < min_y:
        min_y, max_y = y0, y0 + area_h - height
    return max(min_x, min(x, max_x)), max(min_y, min(y, max_y))


def seam_edges(index, monitors):
    """Which sides of monitor `index` touch another monitor.

    `monitors` is a list of (x, y, width, height) tuples.
    """
    if index >= len(monitors):
        return (False, False, False, False)
    x, y, width, height = monitors[index]
    left = right = top = bottom = False
    for other_index, (ox, oy, ow, oh) in enumerate(monitors):
        if other_index == index:
            continue
        overlaps_y = not (oy + oh <= y or oy >= y + height)
        overlaps_x = not (ox + ow <= x or ox >= x + width)
        if overlaps_y and ox + ow == x:
            left = True
        if overlaps_y and ox == x + width:
            right = True
        if overlaps_x and oy + oh == y:
            top = True
        if overlaps_x and oy == y + height:
            bottom = True
    return (left, right, top, bottom)


# --------------------------------------------------------------------------- icons

ICON_FILES = {
    "anthropic": "claude.svg", "anthropic_api": "anthropic.svg",
    "openai": "openai.svg", "copilot": "copilot.svg", "zai": "zhipu.svg",
    "openrouter": "openrouter.svg", "deepseek": "deepseek.svg",
    "kimi": "kimi.svg", "kilo": "kilo.svg", "novita": "novita.svg",
    "moonshot": "moonshot.svg", "grok": "grok.svg",
    "supergrok": "grok.svg", "grokbot": "grokbot.svg",
    "antigravity": "antigravity.svg", "cursor": "cursor.svg",
    "minimax": "minimax.svg", "kiro": "kiro.svg", "nous": "nous.svg",
    "opencode-go": "opencode.svg", "opencode_go": "opencode.svg",
    "ollama": "ollama.svg", "droid": "droid.svg", "devin": "devin.svg",
    "muse-code": "muse-code.svg",
}

BRAND_COLORS = {
    "anthropic": "#d97757", "anthropic_api": "#d97757",
    "google": "#4285f4", "gemini": "#4285f4", "antigravity": "#4285f4",
    "deepseek": "#4d6bfe", "zhipu": "#3d7eff", "zai": "#3d7eff",
    "minimax": "#e5484d", "moonshot": "#7c6cf5", "kimi": "#7c6cf5",
}
THEME_DEFAULT = "vigia"
THEME_FALLBACK = {   # "VigIA Dark", mirrors DESIGN.md
    "surface": "#141418", "surface-border": "#2a2a30",
    "text-primary": "#e6e6ec", "text-secondary": "#9f9fa4", "text-disabled": "#898d98",
    "divider": "#33343a",
    "state-ok": "#4cc38a", "state-warning": "#f2bd34", "state-critical": "#ff6b68",
    "primary": "#8b93ff",
    "menu-surface": "#24252b", "menu-border": "#3a3b42", "menu-hover": "#3a3b42",
}
THEME = dict(THEME_FALLBACK)   # the active theme; mutated in place by set_theme()
THEME_LIGHT = "light"          # what "auto" picks when the system is in light mode
COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def theme_directories():
    """Where DESIGN.md themes may live: env override, next to the code, user copies."""
    here = os.path.dirname(os.path.realpath(__file__))
    directories = []
    override = os.environ.get("VIGIA_THEME_DIR")
    if override:
        directories.append(override)
    directories += [
        os.path.join(here, "themes"),
        os.path.join(HOME, ".local", "share", "vigia", "themes"),
        os.path.join(HOME, ".config", "vigia", "themes"),
    ]
    return [os.path.abspath(directory) for directory in directories]


def parse_theme(path):
    """Read name + colors from a DESIGN.md front matter. Returns None if unusable."""
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return None
    if not lines or lines[0].strip() != "---":
        return None
    name, colors, in_colors = None, {}, False
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line and not line[0].isspace():
            in_colors = line.strip() == "colors:"
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip().strip("\"'")
        elif in_colors and ":" in line:
            key, value = line.split(":", 1)
            value = value.strip().strip("\"'")
            if COLOR_RE.match(value):
                colors[key.strip()] = value
    if not colors:
        return None
    return {"name": name or os.path.splitext(os.path.basename(path))[0], "colors": colors}


def list_themes():
    """[(id, display name)]: the built-in theme first, then every valid theme file."""
    found = {THEME_DEFAULT: "VigIA Dark"}
    for directory in theme_directories():
        for path in sorted(glob.glob(os.path.join(directory, "*.md"))):
            parsed = parse_theme(path)
            if parsed:
                found[os.path.splitext(os.path.basename(path))[0].lower()] = parsed["name"]
    return list(found.items())


def set_theme(name, dark=True, accent=""):
    """Activate a theme by id ("auto" follows `dark`); unknown ids fall back to VigIA Dark.

    A valid `accent` ("#rrggbb") replaces the theme's primary colour."""
    name = str(name).strip().lower()
    if name == "auto":
        name = THEME_DEFAULT if dark else THEME_LIGHT
    colors = dict(THEME_FALLBACK)
    if name != THEME_DEFAULT:
        for directory in theme_directories():
            parsed = parse_theme(os.path.join(directory, name + ".md"))
            if parsed:
                colors.update({k: v for k, v in parsed["colors"].items() if k in colors})
    if re.match(r"^#[0-9a-fA-F]{6}$", str(accent)):
        colors["primary"] = accent
    THEME.clear()
    THEME.update(colors)


def theme_color(key):
    return THEME[key]


def icon_directories():
    """Where provider marks may live: env override, next to the code, installed copies."""
    here = os.path.dirname(os.path.realpath(__file__))
    directories = []
    override = os.environ.get("VIGIA_ICON_DIR")
    if override:
        directories.append(override)
    directories += [
        os.path.join(here, "icons"),
        os.path.join(here, "..", "share", "vigia", "icons"),
        os.path.join(HOME, ".local", "share", "vigia", "icons"),
        os.path.join(HOME, ".local", "share", "ai-usagebar", "tray", "icons"),
    ]
    return [os.path.abspath(directory) for directory in directories]


def icon_path(brand):
    filename = ICON_FILES.get(brand)
    if not filename:
        return None
    for directory in icon_directories():
        path = os.path.join(directory, filename)
        if os.path.isfile(path):
            return path
    return None


def icon_tint(brand, style):
    if style in ("mono", "alert"):
        return THEME["text-secondary"]
    return BRAND_COLORS.get(brand, THEME["text-primary"])


def value_tint(style, percent, warn=60, critical=80):
    """Calm green text, or amber/red once the usage reaches the alert bands."""
    if style != "alert" or not isinstance(percent, (int, float)):
        return THEME["text-primary"]
    if percent >= critical:
        return THEME["state-critical"]
    if percent >= warn:
        return THEME["state-warning"]
    return THEME["state-ok"]


def bar_tint(style, percent, warn=60, critical=80):
    """Usage bar fill: the state colour in alert style, the accent otherwise."""
    if style == "alert" and isinstance(percent, (int, float)):
        return value_tint(style, percent, warn, critical)
    return THEME["primary"]


def is_critical(style, percent, critical=80):
    return style == "alert" and isinstance(percent, (int, float)) and percent >= critical
