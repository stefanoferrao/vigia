# VigIA

🌐 [Português](README.md) · **English** · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md)

[![CI](https://github.com/stefanoferrao/vigia/actions/workflows/ci.yml/badge.svg)](https://github.com/stefanoferrao/vigia/actions/workflows/ci.yml)

> Your AI agents' usage at a glance — a floating pill for Linux and Windows.

![VigIA preview](docs/preview.png)

**Website:** [stefanoferrao.github.io/vigia](https://stefanoferrao.github.io/vigia/en/) — step-by-step install guide, demos and the full config.

VigIA floats over your screen, frameless and without a panel icon, showing how much
of its limit each AI agent has already used. The numbers appear next to the real
icon of each provider (Claude, Codex, OpenCode, Gemini, Grok…) and, if you want,
CPU, RAM and GPU on the same line.

## What it does

- **A single line**: provider icon + percentage of the limit, in the corner you choose.
- **Translucent background** adjustable from 40% to 100% — the text stays sharp.
- **Nine docking positions** (top/middle/bottom × left/center/right).
- **Three sizes** (small, medium, large).
- **Drag and remember**: the position is saved per monitor; with "all", one pill per screen.
- **Never crosses the boundary** between monitors: on shared edges it keeps a margin.
- **Stable width**: the pill does not change size when usage fluctuates.
- **Icons** in three styles: brand color, monochrome, or monochrome with a color alert when usage gets tight.
- **CPU / RAM / GPU** optional, off by default.
- **Which limit to show**: in *What to watch*, choose per provider the window that
  matters — 5h session, weekly, monthly — or a limit of the plan itself, such as
  Claude's `Fable (7d)`. The default is the most consumed one.
- **Island mode**: dock the pill to the top edge like a *Dynamic Island* — only a thin
  strip shows; it opens on mouse hover (or on a click, which pins it open).
- **Five languages**: Portuguese, English, Spanish, French and German (or automatic from the system).
- **Global hotkey** and optional autostart.

## Requirements

- **Python 3.11+** (uses `tomllib`).
- **PySide6** (Qt 6) — the installer creates a private environment and downloads it (~82 MB download, ~245 MB on disk).
- On Linux: **libxcb-cursor0** (the installer tries to handle it; see *Troubleshooting*).
- The **[ai-usagebar](https://github.com/akitaonrails/ai-usagebar)** CLI, which reads the providers' quotas. Builds exist for Linux and Windows.

## Installation

### Linux

```bash
git clone https://github.com/stefanoferrao/vigia.git
cd vigia
./install.sh
```

The installer copies the app to `~/.local/share/vigia`, creates a venv with PySide6,
installs to `~/.local/bin/vigia` and registers the menu shortcut. It recognizes
apt/dnf/pacman when warning about system dependencies.

### Windows 11

In PowerShell, inside the cloned folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

This creates `%LOCALAPPDATA%\vigia` with the venv, PySide6, a Start menu shortcut and
the `vigia.cmd` launcher. Autostart uses the `HKCU\...\Run` key (can be turned off in the menu).

After installing, open it with `vigia` (Linux) or via the **VigIA** shortcut in the Start menu (Windows).

## Usage

On launch, the pill appears in the top-right corner of the primary monitor.

- **Hovering** lightens the background and reveals the settings gear.
- **Dragging** moves the pill; the position is saved per monitor.
- **Gear** (or right click) opens the menu with all the settings. The menu and its
  submenus **stay open** while you change options — only *Hide* and *Quit* close them.
  At the top of the menu are the name and the shortcut in use (`VigIA · Shortcut: Ctrl+Alt+V`).
- **Island mode** (menu → *Dock to top (island)*) leaves only a 120×8 px strip at
  the top, centered; hovering opens the full pill, moving the mouse away collapses it in
  0.4 s, and a **click pins it open** (another click releases it). The strip unfolds in
  200 ms (and collapses in 160 ms), growing from the center, without switching size
  from one frame to the next. Dragging horizontally moves the strip and the position is saved
  per monitor.
- **Default shortcut `Ctrl+Alt+V`** shows/hides (and starts it, if not running).
- **Really quitting** is done via menu → *Quit*.

> Shortcuts starting with `Super` are usually captured by the system before
> reaching the app. That is why the default is `Ctrl+Alt+V`; changing it is one line in the config.

## Configuration

Linux: `~/.config/vigia/vigia.toml` · Windows: `%APPDATA%\vigia\vigia.toml`.
The menu writes to this file; manual edits are applied with `vigia --reload`.

```toml
[overlay]
opacity = 0.82          # 0.40 to 1.00 — transparency of the background only
size = "medium"         # small | medium | large
icon_style = "brand"    # brand | mono | alert
monitor = "primary"     # primary | secondary | all | "0", "1", ...
anchor = "top-right"    # top-left | top-center | top-right
                        # middle-left | middle-center | middle-right
                        # bottom-left | bottom-center | bottom-right
island = false          # true: docks at the top as a thin strip (island mode)
always_on_top = true
show_system = false     # CPU / RAM / GPU
autostart = true
refresh_minutes = 5     # 1 to 60
max_providers = 4       # 1 to 8
hotkey = "<Control><Alt>v"
language = "auto"       # auto | pt | en | es | fr | de
alert_warn = 60         # icon_style = "alert": amber from here
alert_critical = 80     # ... and red from here
hide_providers = ""     # comma-separated ids: "openai,gemini"
hide_system = ""        # "cpu,ram,gpu" to hide system items

[overlay.metrics]       # which limit each provider shows (default: the highest usage)
anthropic = "Weekly (7d)"
"opencode-go" = "Rolling (5h)"

[overlay.island_offsets] # horizontal offset of the island on each monitor
"HDMI-A-0" = -40
```

To choose what appears, use the **Items** menu (a checkbox per provider and per
CPU/RAM/GPU) — the choice goes to `hide_providers` and `hide_system`. Hidden items
remain listed in the menu, so you can bring them back. With `icon_style =
"alert"`, the numbers turn amber and red according to `alert_warn` / `alert_critical`.

The `[overlay.positions]` table stores each monitor's offset (key = screen
name) after a drag — you don't need to touch it. *Reset position* in the
menu clears these values and returns to the chosen docking. In island mode the same applies
to `[overlay.island_offsets]`, which stores only the horizontal offset.

## Themes

The look follows the [DESIGN.md](https://github.com/google-labs-code/design.md) format: each theme is a `.md` file whose front matter defines the colors (`surface`, `text-primary`, `state-ok`, `state-warning`, `state-critical`, `primary`, ...). The default theme is the [`DESIGN.md`](DESIGN.md) at the root.

Included themes in [`themes/`](themes/): Midnight, Graphite, Light, Aurora, Sunset and Mono High Contrast (AAA). Choose via gear → **Theme**, or use **Automatic (system)** to switch between dark and light following the system. **Accent color…** (in the same submenu) changes the main color of any theme. Each number gets a thin usage bar (**Progress bars** menu), and in "Alert by usage" mode critical values pulse gently (**Pulse on critical state** menu). To create your own, copy a file from `themes/` to `~/.config/vigia/themes/`, edit the colors and validate with `npx @google/design.md lint <file>`; it appears in the menu.

## Languages

The default is **Automatic** (follows the system locale; on Windows, the interface
language). To pin one, use the **Language** menu or `language = "en"`.
Available: `pt`, `en`, `es`, `fr`, `de`.

## Command line

| Command | What it does |
|---|---|
| `vigia` | opens the pill (shows the existing instance, if any) |
| `vigia --show` | shows, starting if needed |
| `vigia --toggle` | shows/hides (good for a shortcut) |
| `vigia --reload` | rereads the config without restarting |
| `vigia --quit` | stops the instance |
| `vigia --version` | prints the version |

## How data is read

- **Providers**: `ai-usagebar usage --json`, every 5 minutes. Each pill shows one
  limit of that provider: the one chosen in *What to watch* or, by default, the most consumed.
- **CPU/RAM**: `psutil` when available; on Linux, `/proc/stat` and `/proc/meminfo`; on Windows, the system API.
- **GPU**: `gpu_busy_percent` from `sysfs` (Linux) or `nvidia-smi` (when present).

Nothing leaves your machine beyond the calls `ai-usagebar` already makes.

## Structure

```
vigia            launcher (Python)
vigia_qt.py      Qt interface — the same on both systems
vigia_core.py    data, config, languages, themes, metrics
DESIGN.md        default theme (DESIGN.md format)
themes/          extra themes: Midnight, Graphite, Light, Aurora, Sunset, Mono HC
icons/           provider brands (SVG)
assets/          app icon and gear
tests/           core tests and Qt smoke test
install.sh       Linux installer
install.ps1      Windows installer
```

## Known limitations

- **Wayland**: the global shortcut and free window positioning are restricted by the
  compositor. The pill appears, but the `hotkey` may not work — use the desktop's
  own shortcut calling `vigia --toggle`.
- **Windows 11**: the code is the same and CI runs the tests on `windows-latest`,
  but the visual validation was done on Linux/X11. If something is out of place,
  open an issue with a screenshot.
- The GPU depends on the driver exposing `gpu_busy_percent` (Linux) or on `nvidia-smi`
  existing; without that, the item is omitted (instead of showing zero).
- The Spanish, French and German translations are a first pass — corrections are welcome.

## Troubleshooting

- **Qt won't open (Linux)**: `libxcb-cursor0` is missing → `sudo apt install libxcb-cursor0`
  (Fedora: `xcb-util-cursor`; Arch: `xcb-util-cursor`). The installer tries to handle it.
- **Nothing shows in the pill**: run `ai-usagebar usage --json` and check whether there is data.
- **No shortcut on Wayland**: see *Known limitations*.
- **Log**: Linux `~/.cache/vigia/vigia.log` · Windows `%LOCALAPPDATA%\vigia\vigia.log`.

## Uninstallation

Linux:

```bash
vigia --quit
rm -f  ~/.local/bin/vigia
rm -rf ~/.local/share/vigia ~/.config/vigia
rm -f  ~/.local/share/applications/vigia.desktop ~/.config/autostart/vigia.desktop
rm -f  ~/.local/share/icons/hicolor/scalable/apps/vigia.svg
```

Windows (PowerShell):

```powershell
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\vigia"
Remove-Item -Recurse -Force "$env:APPDATA\vigia"
Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\VigIA.lnk"
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name VigIA
```

## Credits

- Quota data: [ai-usagebar](https://github.com/akitaonrails/ai-usagebar).
- The provider icons are trademarks of their respective owners, used here only
  for identification, and come from the `ai-usagebar`/Omarchy package.

## License

MIT — see [LICENSE](LICENSE).
