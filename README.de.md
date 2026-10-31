# VigIA

[![CI](https://github.com/stefanoferrao/vigia/actions/workflows/ci.yml/badge.svg)](https://github.com/stefanoferrao/vigia/actions/workflows/ci.yml)

🌐 [Português](README.md) · [English](README.en.md) · [Español](README.es.md) · [Français](README.fr.md) · **Deutsch**

> Die Nutzung deiner KI-Agenten auf einen Blick — eine schwebende Pille für Linux und Windows.

![Vorschau von VigIA](docs/preview.png)

**Website:** [stefanoferrao.github.io/vigia](https://stefanoferrao.github.io/vigia/de/) — Installationsanleitung, Demos und die vollständige Config.

VigIA liegt über dem Bildschirm, ohne Rahmen und ohne Symbol in der Leiste, und zeigt,
wie viel von seinem Limit jeder KI-Agent schon verbraucht hat. Die Zahlen erscheinen neben
dem echten Symbol jedes Anbieters (Claude, Codex, OpenCode, Gemini, Grok…) und, wenn du
möchtest, CPU, RAM und GPU in derselben Zeile.

## Was es kann

- **Nur eine Zeile**: Symbol des Anbieters + Prozent des Limits, in der Ecke deiner Wahl.
- **Durchscheinender Hintergrund**, einstellbar von 40 % bis 100 % — der Text bleibt scharf.
- **Neun Andockpositionen** (oben/Mitte/unten × links/Mitte/rechts).
- **Drei Größen** (klein, mittel, groß).
- **Ziehen und merken**: Die Position wird pro Monitor gespeichert; bei „Beide“ eine Pille pro Bildschirm.
- **Überschreitet nie die Grenze** zwischen Monitoren: An gemeinsamen Rändern hält sie Abstand.
- **Stabile Breite**: Die Pille ändert ihre Größe nicht, wenn die Nutzung schwankt.
- **Symbole** in drei Stilen: Markenfarbe, einfarbig oder einfarbig mit Farbwarnung, wenn die Nutzung knapp wird.
- **CPU / RAM / GPU** optional, standardmäßig aus.
- **Welches Limit angezeigt wird**: Unter *Was überwachen* wählst du pro Anbieter das Fenster,
  das zählt — 5-Stunden-Sitzung, wöchentlich, monatlich — oder ein Limit des Tarifs selbst, wie
  `Fable (7d)` bei Claude. Standard ist das am stärksten verbrauchte.
- **Inselmodus**: Dock die Pille am oberen Rand wie eine *Dynamic Island* — nur ein schmaler
  Streifen ist sichtbar; er öffnet sich beim Darüberfahren mit der Maus (oder per Klick, der ihn offen fixiert).
  Die Insel lässt sich frei ziehen und **rastet an der nächsten Kante ein** (oben, unten, links oder rechts). *Position der Insel* bietet 12 Andockplätze (Kante × Position entlang der Kante).
- **Fünf Sprachen**: Portugiesisch, Englisch, Spanisch, Französisch und Deutsch (oder automatisch nach System).
- **Globales Tastenkürzel** und optionaler Autostart.

## Voraussetzungen

- **Python 3.11+** (nutzt `tomllib`).
- **PySide6** (Qt 6) — das Installationsprogramm erstellt eine private Umgebung und lädt es herunter (~82 MB Download, ~245 MB auf der Platte).
- Unter Linux: **libxcb-cursor0** (das Installationsprogramm versucht, es zu lösen; siehe *Probleme?*).
- **[ai-usagebar](https://github.com/akitaonrails/ai-usagebar)**, das die Kontingente der Anbieter ausliest, ist **eingebaut**: Der Installer (oder der erste Start) lädt die offizielle Binärdatei, prüft ihre sha256 und legt sie in `~/.local/share/vigia/bin` ab (Windows: `%LOCALAPPDATA%\vigia\bin`). Aktualisieren über **Datenquelle aktualisieren** im Menü.

## Installation

### Linux

```bash
git clone https://github.com/stefanoferrao/vigia.git
cd vigia
./install.sh
```

Das Installationsprogramm kopiert die App nach `~/.local/share/vigia`, erstellt ein venv mit PySide6,
installiert nach `~/.local/bin/vigia` und registriert die Menüverknüpfung. Es erkennt
apt/dnf/pacman, wenn es auf Systemabhängigkeiten hinweist.

### Windows 11

In PowerShell, im geklonten Ordner:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Das erstellt `%LOCALAPPDATA%\vigia` mit dem venv, PySide6, einer Verknüpfung im Startmenü und
dem Launcher `vigia.cmd`. Der Autostart nutzt den Schlüssel `HKCU\...\Run` (im Menü abschaltbar).

Nach der Installation öffnest du mit `vigia` (Linux) oder über die Verknüpfung **VigIA** im Startmenü (Windows).

## Nutzung

Beim Öffnen erscheint die Pille in der oberen rechten Ecke des Hauptmonitors.

- **Mit der Maus darüberfahren** hellt den Hintergrund auf und blendet das Einstellungs-Zahnrad ein.
- **Ziehen** bewegt die Pille; die Position wird pro Monitor gespeichert.
- **Zahnrad** (oder Rechtsklick) öffnet das Menü mit allen Einstellungen. Das Menü und die
  Untermenüs **bleiben offen**, während du Optionen änderst — nur *Ausblenden* und *Beenden* schließen sie.
  Oben im Menü stehen der Name und das aktive Tastenkürzel (`VigIA · Tastenkürzel: Ctrl+Alt+V`).
- **Inselmodus** (Menü → *Oben andocken (Insel)*) lässt nur einen 120×8-px-Streifen oben,
  zentriert; Darüberfahren öffnet die ganze Pille, Wegbewegen der Maus fährt sie nach
  0,4 s wieder ein, und ein **Klick fixiert sie offen** (ein weiterer Klick löst sie). Der Streifen klappt in
  200 ms auf (und fährt in 160 ms ein), wächst von der Mitte aus, ohne die Größe von
  einem Frame zum nächsten zu wechseln. Horizontales Ziehen verschiebt den Streifen, und die Position wird
  pro Monitor gespeichert.
- **Standard-Tastenkürzel `Ctrl+Alt+V`** zeigt/versteckt (und startet, falls es nicht läuft).
- **Wirklich beenden** geht über Menü → *Beenden*.

> Kürzel, die mit `Super` beginnen, werden meist vom System abgefangen, bevor sie
> die App erreichen. Deshalb ist der Standard `Ctrl+Alt+V`; ändern ist eine Zeile in der Config.

## Konfiguration

Linux: `~/.config/vigia/vigia.toml` · Windows: `%APPDATA%\vigia\vigia.toml`.
Das Menü schreibt in diese Datei; manuelle Änderungen werden mit `vigia --reload` übernommen.

```toml
[overlay]
opacity = 0.82          # 0.40 bis 1.00 — Transparenz nur des Hintergrunds
size = "medium"         # small | medium | large
icon_style = "brand"    # brand | mono | alert
monitor = "primary"     # primary | secondary | all | "0", "1", ...
anchor = "top-right"    # top-left | top-center | top-right
                        # middle-left | middle-center | middle-right
                        # bottom-left | bottom-center | bottom-right
island = false          # true: dockt oben als schmaler Streifen an (Inselmodus)
island_anchor = "top-center" # Kante-Position: top|bottom-left|center|right, left|right-top|middle|bottom
always_on_top = true
show_system = false     # CPU / RAM / GPU
autostart = true
refresh_minutes = 5     # 1 bis 60
max_providers = 4       # 1 bis 8
hotkey = "<Control><Alt>v"
language = "auto"       # auto | pt | en | es | fr | de
alert_warn = 60         # icon_style = "alert": ab hier bernstein
alert_critical = 80     # ... und ab hier rot
hide_providers = ""     # durch Komma getrennte IDs: "openai,gemini"
hide_system = ""        # "cpu,ram,gpu", um Systemelemente auszublenden

[overlay.metrics]       # welches Limit jeder Anbieter zeigt (Standard: die höchste Nutzung)
anthropic = "Weekly (7d)"
"opencode-go" = "Rolling (5h)"

[overlay.island_offsets] # horizontaler Versatz der Insel auf jedem Monitor
"HDMI-A-0" = -40
```

Um festzulegen, was angezeigt wird, nutze das Menü **Elemente** (Kontrollkästchen pro Anbieter und für
CPU/RAM/GPU) — die Auswahl landet in `hide_providers` und `hide_system`. Ausgeblendete Elemente
bleiben im Menü aufgelistet, sodass du sie zurückholen kannst. Mit `icon_style =
"alert"` werden die Zahlen bernstein und rot gemäß `alert_warn` / `alert_critical`.

Die Tabelle `[overlay.positions]` speichert den Versatz jedes Monitors (Schlüssel = Name
des Bildschirms) nach einem Ziehen — du musst sie nicht anfassen. *Position zurücksetzen* im
Menü löscht diese Werte und kehrt zur gewählten Andockposition zurück. Im Inselmodus gilt dasselbe
für `[overlay.island_offsets]`, das nur den horizontalen Versatz speichert.

## Designs

Das Aussehen folgt dem Format [DESIGN.md](https://github.com/google-labs-code/design.md): Jedes Design ist eine `.md`-Datei, deren Front Matter die Farben definiert (`surface`, `text-primary`, `state-ok`, `state-warning`, `state-critical`, `primary`, ...). Das Standarddesign ist die [`DESIGN.md`](DESIGN.md) im Wurzelverzeichnis.

Enthaltene Designs in [`themes/`](themes/): Midnight, Graphite, Light, Aurora, Sunset und Mono High Contrast (AAA). Wähle unter Zahnrad → **Design**, oder nutze **Automatisch (System)**, um je nach System zwischen dunkel und hell zu wechseln. **Akzentfarbe…** (im selben Untermenü) ändert die Hauptfarbe jedes Designs. Jede Zahl bekommt einen schmalen Nutzungsbalken (Menü **Fortschrittsbalken**), und im Modus „Nutzungswarnung“ pulsieren kritische Werte sanft (Menü **Pulsieren bei kritischem Wert**). Um ein eigenes zu erstellen, kopiere eine Datei aus `themes/` nach `~/.config/vigia/themes/`, bearbeite die Farben und validiere mit `npx @google/design.md lint <Datei>`; es erscheint im Menü.

## Sprachen

Standard ist **Automatisch** (folgt dem Locale des Systems; unter Windows der Sprache der
Oberfläche). Zum Festlegen nutze das Menü **Sprache** oder `language = "en"`.
Verfügbar: `pt`, `en`, `es`, `fr`, `de`.

## Kommandozeile

| Befehl | Was er tut |
|---|---|
| `vigia` | öffnet die Pille (zeigt die vorhandene Instanz, falls es eine gibt) |
| `vigia --show` | zeigt, startet bei Bedarf |
| `vigia --toggle` | zeigt/versteckt (gut für ein Tastenkürzel) |
| `vigia --reload` | liest die Config neu, ohne Neustart |
| `vigia --quit` | beendet die Instanz |
| `vigia --version` | gibt die Version aus |

## Wie die Daten gelesen werden

- **Anbieter**: `ai-usagebar usage --json`, alle 5 Minuten. Jede Pille zeigt ein
  Limit dieses Anbieters: das unter *Was überwachen* gewählte oder standardmäßig das am stärksten verbrauchte.
- **CPU/RAM**: `psutil`, wenn verfügbar; unter Linux `/proc/stat` und `/proc/meminfo`; unter Windows die System-API.
- **GPU**: `gpu_busy_percent` aus `sysfs` (Linux) oder `nvidia-smi` (falls vorhanden).

Nichts verlässt deinen Rechner außer den Aufrufen, die `ai-usagebar` ohnehin macht.

## Struktur

```
vigia            Launcher (Python)
vigia_qt.py      Qt-Oberfläche — auf beiden Systemen dieselbe
vigia_core.py    Daten, Config, Sprachen, Designs, Metriken
DESIGN.md        Standarddesign (DESIGN.md-Format)
themes/          zusätzliche Designs: Midnight, Graphite, Light, Aurora, Sunset, Mono HC
icons/           Marken der Anbieter (SVG)
assets/          App-Symbol und Zahnrad
tests/           Tests des Kerns und Qt-Smoke-Test
install.sh       Linux-Installationsprogramm
install.ps1      Windows-Installationsprogramm
```

## Bekannte Einschränkungen

- **Wayland**: Globales Tastenkürzel und freie Fensterpositionierung sind durch den
  Compositor eingeschränkt. Die Pille erscheint, aber der `hotkey` funktioniert eventuell nicht — nutze das Kürzel
  des Desktops selbst, das `vigia --toggle` aufruft.
- **Windows 11**: Der Code ist derselbe und die CI führt die Tests auf `windows-latest` aus,
  aber die visuelle Prüfung erfolgte unter Linux/X11. Wenn etwas nicht am richtigen Platz ist,
  eröffne ein Issue mit Screenshot.
- Die GPU hängt davon ab, dass der Treiber `gpu_busy_percent` bereitstellt (Linux) oder `nvidia-smi`
  vorhanden ist; ohne das wird das Element weggelassen (statt null anzuzeigen).
- Die Übersetzungen ins Spanische, Französische und Deutsche sind ein erster Wurf — Korrekturen sind willkommen.

## Probleme?

- **Qt öffnet nicht (Linux)**: `libxcb-cursor0` fehlt → `sudo apt install libxcb-cursor0`
  (Fedora: `xcb-util-cursor`; Arch: `xcb-util-cursor`). Das Installationsprogramm versucht, es zu lösen.
- **In der Pille erscheint nichts**: Führe `ai-usagebar usage --json` aus und prüfe, ob Daten vorhanden sind.
- **Kein Tastenkürzel unter Wayland**: siehe *Bekannte Einschränkungen*.
- **Log**: Linux `~/.cache/vigia/vigia.log` · Windows `%LOCALAPPDATA%\vigia\vigia.log`.

## Deinstallation

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

## Danksagung

- Kontingentdaten: [ai-usagebar](https://github.com/akitaonrails/ai-usagebar).
- Die Symbole der Anbieter sind Marken der jeweiligen Inhaber, hier nur zur
  Identifikation verwendet, und stammen aus dem Paket von `ai-usagebar`/Omarchy.

## Lizenz

MIT — siehe [LICENSE](LICENSE).
