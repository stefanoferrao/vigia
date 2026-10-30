# VigIA

🌐 [Português](README.md) · [English](README.en.md) · **Español** · [Français](README.fr.md) · [Deutsch](README.de.md)

[![CI](https://github.com/stefanoferrao/vigia/actions/workflows/ci.yml/badge.svg)](https://github.com/stefanoferrao/vigia/actions/workflows/ci.yml)

> El uso de tus agentes de IA de un vistazo — una píldora flotante para Linux y Windows.

![Vista previa de VigIA](docs/preview.png)

**Sitio:** [stefanoferrao.github.io/vigia](https://stefanoferrao.github.io/vigia/es/) — guía de instalación paso a paso, demostraciones y el config completo.

VigIA se queda sobre la pantalla, sin marco y sin icono en el panel, mostrando cuánto
de su límite ha consumido ya cada agente de IA. Los números aparecen junto al icono
real de cada proveedor (Claude, Codex, OpenCode, Gemini, Grok…) y, si quieres,
CPU, RAM y GPU en la misma línea.

## Qué hace

- **Una sola línea**: icono del proveedor + porcentaje del límite, en la esquina que elijas.
- **Fondo translúcido** ajustable del 40% al 100% — el texto sigue nítido.
- **Nueve posiciones** de anclaje (arriba/medio/abajo × izquierda/centro/derecha).
- **Tres tamaños** (pequeño, mediano, grande).
- **Se arrastra y recuerda** la posición de cada monitor; en "ambos", una píldora por pantalla.
- **Nunca cruza la división** entre monitores: en los bordes compartidos mantiene un margen.
- **Ancho estable**: la píldora no cambia de tamaño cuando el uso oscila.
- **Iconos** en tres estilos: color de marca, monocromático, o monocromático con alerta de color cuando el uso aprieta.
- **CPU / RAM / GPU** opcionales, desactivados por defecto.
- **Qué límite mostrar**: en *Qué vigilar*, elige por proveedor la ventana que
  importa — sesión de 5h, semanal, mensual — o un límite del propio plan, como el
  `Fable (7d)` de Claude. Por defecto se muestra el más consumido.
- **Modo isla**: ancla la píldora al borde superior como una *Dynamic Island* — solo
  se ve una franja fina; se abre al pasar el ratón (o con un clic, que la fija abierta).
- **Cinco idiomas**: portugués, inglés, español, francés y alemán (o automático según el sistema).
- **Atajo global** y autostart opcional.

## Requisitos

- **Python 3.11+** (usa `tomllib`).
- **PySide6** (Qt 6) — el instalador crea un entorno privado y lo descarga (~82 MB de descarga, ~245 MB en disco).
- En Linux: **libxcb-cursor0** (el instalador intenta resolverlo; ve *¿Problemas?*).
- El CLI **[ai-usagebar](https://github.com/akitaonrails/ai-usagebar)**, que lee las cuotas de los proveedores. Hay builds para Linux y Windows.

## Instalación

### Linux

```bash
git clone https://github.com/stefanoferrao/vigia.git
cd vigia
./install.sh
```

El instalador copia la app a `~/.local/share/vigia`, crea un venv con PySide6,
instala en `~/.local/bin/vigia` y registra el acceso directo del menú. Reconoce
apt/dnf/pacman al avisar sobre dependencias del sistema.

### Windows 11

En PowerShell, dentro de la carpeta clonada:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Esto crea `%LOCALAPPDATA%\vigia` con el venv, PySide6, un acceso directo en el menú Inicio y
el launcher `vigia.cmd`. El autostart usa la clave `HKCU\...\Run` (se puede desactivar en el menú).

Tras instalar, ábrelo con `vigia` (Linux) o con el acceso directo **VigIA** del menú Inicio (Windows).

## Uso

Al abrirse, la píldora aparece en la esquina superior derecha del monitor principal.

- **Pasar el ratón** aclara el fondo y revela el engranaje de ajustes.
- **Arrastrar** mueve la píldora; la posición queda guardada por monitor.
- **Engranaje** (o botón derecho) abre el menú con todos los ajustes. El menú y los
  submenús **permanecen abiertos** mientras cambias las opciones — solo *Ocultar* y *Salir* los cierran.
  En la parte superior del menú están el nombre y el atajo en uso (`VigIA · Atajo: Ctrl+Alt+V`).
- **Modo isla** (menú → *Anclar arriba (isla)*) deja solo una franja de 120×8 px en
  la parte superior, centrada; al pasar el ratón se abre la píldora completa, al sacarlo se contrae
  en 0,4 s, y un **clic la fija abierta** (otro clic la libera). La franja se despliega en
  200 ms (y se contrae en 160 ms) creciendo desde el centro, sin cambiar de tamaño
  de un fotograma al siguiente. Arrastrar en horizontal mueve la franja y la posición queda guardada
  por monitor.
- **El atajo predeterminado `Ctrl+Alt+V`** muestra/oculta (e inicia, si no está en ejecución).
- **Salir de verdad** se hace desde el menú → *Salir*.

> Los atajos que empiezan con `Super` suelen ser capturados por el sistema antes de
> llegar a la app. Por eso el predeterminado es `Ctrl+Alt+V`; cambiarlo es una línea en el config.

## Configuración

Linux: `~/.config/vigia/vigia.toml` · Windows: `%APPDATA%\vigia\vigia.toml`.
El menú escribe en ese archivo; las ediciones manuales se aplican con `vigia --reload`.

```toml
[overlay]
opacity = 0.82          # 0.40 a 1.00 — transparencia solo del fondo
size = "medium"         # small | medium | large
icon_style = "brand"    # brand | mono | alert
monitor = "primary"     # primary | secondary | all | "0", "1", ...
anchor = "top-right"    # top-left | top-center | top-right
                        # middle-left | middle-center | middle-right
                        # bottom-left | bottom-center | bottom-right
island = false          # true: ancla arriba como una franja fina (modo isla)
always_on_top = true
show_system = false     # CPU / RAM / GPU
autostart = true
refresh_minutes = 5     # 1 a 60
max_providers = 4       # 1 a 8
hotkey = "<Control><Alt>v"
language = "auto"       # auto | pt | en | es | fr | de
alert_warn = 60         # icon_style = "alert": ámbar a partir de aquí
alert_critical = 80     # ... y rojo a partir de aquí
hide_providers = ""     # ids separados por coma: "openai,gemini"
hide_system = ""        # "cpu,ram,gpu" para ocultar elementos del sistema

[overlay.metrics]       # qué límite muestra cada proveedor (por defecto: el mayor uso)
anthropic = "Weekly (7d)"
"opencode-go" = "Rolling (5h)"

[overlay.island_offsets] # desplazamiento horizontal de la isla en cada monitor
"HDMI-A-0" = -40
```

Para elegir qué aparece, usa el menú **Elementos** (casilla por proveedor y por
CPU/RAM/GPU) — la elección va a `hide_providers` y `hide_system`. Los elementos ocultos
siguen listados en el menú, así que se pueden volver a mostrar. Con `icon_style =
"alert"`, los números se vuelven ámbar y rojos según `alert_warn` / `alert_critical`.

La tabla `[overlay.positions]` guarda el desplazamiento de cada monitor (clave = nombre
de la pantalla) después de un arrastre — no hace falta tocarla. *Restaurar posición* en el
menú borra esos valores y vuelve al anclaje elegido. En el modo isla ocurre lo mismo
con `[overlay.island_offsets]`, que guarda solo el desplazamiento horizontal.

## Temas

El aspecto sigue el formato [DESIGN.md](https://github.com/google-labs-code/design.md): cada tema es un archivo `.md` cuyo front matter define los colores (`surface`, `text-primary`, `state-ok`, `state-warning`, `state-critical`, `primary`, ...). El tema predeterminado es el [`DESIGN.md`](DESIGN.md) de la raíz.

Temas incluidos en [`themes/`](themes/): Midnight, Graphite, Light, Aurora, Sunset y Mono High Contrast (AAA). Elige en engranaje → **Tema**, o usa **Automático (sistema)** para alternar entre oscuro y claro según el sistema. **Color de acento…** (en el mismo submenú) cambia el color principal de cualquier tema. Cada número gana una barra fina de uso (menú **Barras de progreso**), y en el modo "Alerta por uso" los valores críticos pulsan suavemente (menú **Pulsar en estado crítico**). Para crear el tuyo, copia un archivo de `themes/` a `~/.config/vigia/themes/`, edita los colores y valida con `npx @google/design.md lint <archivo>`; aparecerá en el menú.

## Idiomas

El valor predeterminado es **Automático** (sigue el locale del sistema; en Windows, el idioma de la
interfaz). Para fijarlo, usa el menú **Idioma** o `language = "en"`.
Disponibles: `pt`, `en`, `es`, `fr`, `de`.

## Línea de comandos

| Comando | Qué hace |
|---|---|
| `vigia` | abre la píldora (muestra la instancia existente, si la hay) |
| `vigia --show` | muestra, iniciando si es necesario |
| `vigia --toggle` | muestra/oculta (bueno para un atajo) |
| `vigia --reload` | relee el config sin reiniciar |
| `vigia --quit` | termina la instancia |
| `vigia --version` | imprime la versión |

## Cómo se leen los datos

- **Proveedores**: `ai-usagebar usage --json`, cada 5 minutos. Cada píldora muestra un
  límite de ese proveedor: el elegido en *Qué vigilar* o, por defecto, el más consumido.
- **CPU/RAM**: `psutil` cuando está disponible; en Linux, `/proc/stat` y `/proc/meminfo`; en Windows, la API del sistema.
- **GPU**: `gpu_busy_percent` de `sysfs` (Linux) o `nvidia-smi` (cuando existe).

Nada sale de tu máquina aparte de las llamadas que `ai-usagebar` ya hace.

## Estructura

```
vigia            launcher (Python)
vigia_qt.py      interfaz Qt — la misma en los dos sistemas
vigia_core.py    datos, config, idiomas, temas, métricas
DESIGN.md        tema predeterminado (formato DESIGN.md)
themes/          temas extra: Midnight, Graphite, Light, Aurora, Sunset, Mono HC
icons/           marcas de los proveedores (SVG)
assets/          icono de la app y engranaje
tests/           pruebas del núcleo y smoke de Qt
install.sh       instalador Linux
install.ps1      instalador Windows
```

## Limitaciones conocidas

- **Wayland**: el atajo global y el posicionamiento libre de ventanas están restringidos por el
  compositor. La píldora aparece, pero el `hotkey` puede no funcionar — usa el atajo
  del propio escritorio llamando a `vigia --toggle`.
- **Windows 11**: el código es el mismo y el CI ejecuta las pruebas en `windows-latest`,
  pero la validación visual se hizo en Linux/X11. Si algo está fuera de lugar,
  abre un issue con la captura.
- La GPU depende de que el driver exponga `gpu_busy_percent` (Linux) o de que
  exista `nvidia-smi`; sin eso, el elemento se omite (en vez de mostrar cero).
- Las traducciones al español, francés y alemán son una primera pasada — las correcciones son bienvenidas.

## ¿Problemas?

- **Qt no abre (Linux)**: falta `libxcb-cursor0` → `sudo apt install libxcb-cursor0`
  (Fedora: `xcb-util-cursor`; Arch: `xcb-util-cursor`). El instalador intenta resolverlo.
- **No aparece nada en la píldora**: ejecuta `ai-usagebar usage --json` y comprueba si hay datos.
- **Sin atajo en Wayland**: ve *Limitaciones*.
- **Log**: Linux `~/.cache/vigia/vigia.log` · Windows `%LOCALAPPDATA%\vigia\vigia.log`.

## Desinstalación

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

## Créditos

- Datos de cuota: [ai-usagebar](https://github.com/akitaonrails/ai-usagebar).
- Los iconos de los proveedores son marcas de sus respectivos dueños, usados aquí solo
  para identificación, y vienen del paquete de `ai-usagebar`/Omarchy.

## Licencia

MIT — ve [LICENSE](LICENSE).
