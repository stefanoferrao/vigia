# VigIA

[![CI](https://github.com/stefanoferrao/vigia/actions/workflows/ci.yml/badge.svg)](https://github.com/stefanoferrao/vigia/actions/workflows/ci.yml)

🌐 [Português](README.md) · [English](README.en.md) · [Español](README.es.md) · **Français** · [Deutsch](README.de.md)

> L'usage de vos agents IA en un coup d'œil — une pastille flottante pour Linux et Windows.

![Aperçu de VigIA](docs/preview.png)

**Site :** [stefanoferrao.github.io/vigia](https://stefanoferrao.github.io/vigia/fr/) — guide d'installation pas à pas, démonstrations et configuration complète.

VigIA reste au-dessus de l'écran, sans cadre et sans icône dans la barre des tâches,
et montre quelle part de sa limite chaque agent IA a déjà consommée. Les chiffres
s'affichent à côté de la vraie icône de chaque fournisseur (Claude, Codex, OpenCode,
Gemini, Grok…) et, si vous le souhaitez, le CPU, la RAM et le GPU sur la même ligne.

## Ce qu'il fait

- **Une seule ligne** : icône du fournisseur + pourcentage de la limite, dans le coin de votre choix.
- **Fond translucide** réglable de 40 % à 100 % — le texte reste net.
- **Neuf positions** d'ancrage (haut/milieu/bas × gauche/centre/droite).
- **Trois tailles** (petit, moyen, grand).
- **Se déplace par glisser et mémorise** la position de chaque écran ; avec « les deux », une pastille par écran.
- **Ne franchit jamais la frontière** entre écrans : sur les bords partagés, elle garde une marge.
- **Largeur stable** : la pastille ne change pas de taille quand l'usage fluctue.
- **Icônes** en trois styles : couleur de la marque, monochrome, ou monochrome avec alerte de couleur quand l'usage grimpe.
- **CPU / RAM / GPU** optionnels, désactivés par défaut.
- **Quelle limite afficher** : dans *Quoi surveiller*, choisissez pour chaque fournisseur la
  fenêtre qui compte — session de 5 h, hebdomadaire, mensuelle — ou une limite propre au plan, comme
  `Fable (7d)` de Claude. Par défaut, c'est la plus consommée.
- **Mode île** : ancrez la pastille au bord supérieur comme une *Dynamic Island* — seule une
  fine bande apparaît ; elle s'ouvre au survol de la souris (ou d'un clic, qui la garde ouverte).
  Glisser l'île la dépose n'importe où et elle **se colle au bord le plus proche** (haut, bas, gauche ou droite). *Position de l'île* propose 12 ancrages (bord × position sur le bord).
- **Cinq langues** : portugais, anglais, espagnol, français et allemand (ou automatique selon le système).
- **Raccourci global** et démarrage automatique optionnel.

## Prérequis

- **Python 3.11+** (utilise `tomllib`).
- **PySide6** (Qt 6) — l'installateur crée un environnement privé et le télécharge (~82 Mo à télécharger, ~245 Mo sur disque).
- Sous Linux : **libxcb-cursor0** (l'installateur essaie de le résoudre ; voir *Un problème ?*).
- **[ai-usagebar](https://github.com/akitaonrails/ai-usagebar)**, qui lit les quotas des fournisseurs, est **intégré** : l'installateur (ou le premier lancement) télécharge le binaire officiel, vérifie son sha256 et le garde dans `~/.local/share/vigia/bin` (Windows : `%LOCALAPPDATA%\vigia\bin`). Mise à jour via **Mettre à jour la source de données** dans le menu.

## Installation

### Linux

```bash
git clone https://github.com/stefanoferrao/vigia.git
cd vigia
./install.sh
```

L'installateur copie l'application dans `~/.local/share/vigia`, crée un venv avec PySide6,
installe dans `~/.local/bin/vigia` et enregistre le raccourci de menu. Il reconnaît
apt/dnf/pacman pour signaler les dépendances système.

### Windows 11

Dans PowerShell, à l'intérieur du dossier cloné :

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Cela crée `%LOCALAPPDATA%\vigia` avec le venv, PySide6, un raccourci dans le menu Démarrer et
le lanceur `vigia.cmd`. Le démarrage automatique utilise la clé `HKCU\...\Run` (désactivable dans le menu).

Après l'installation, ouvrez avec `vigia` (Linux) ou via le raccourci **VigIA** du menu Démarrer (Windows).

## Utilisation

À l'ouverture, la pastille apparaît dans le coin supérieur droit de l'écran principal.

- **Survoler** avec la souris éclaircit le fond et révèle l'engrenage des réglages.
- **Glisser** déplace la pastille ; la position est enregistrée par écran.
- **Engrenage** (ou clic droit) ouvre le menu avec tous les réglages. Le menu et les
  sous-menus **restent ouverts** pendant que vous changez les options — seuls *Masquer* et *Quitter* le ferment.
  En haut du menu figurent le nom et le raccourci utilisé (`VigIA · Raccourci : Ctrl+Alt+V`).
- **Mode île** (menu → *Ancrer en haut (île)*) ne laisse qu'une bande de 120×8 px en
  haut, centrée ; survoler ouvre la pastille entière, quitter la souris la replie en
  0,4 s, et un **clic la garde ouverte** (un autre clic la libère). La bande se déploie en
  200 ms (et se replie en 160 ms) en grandissant depuis le centre, sans changer de taille
  d'une image à l'autre. Glisser à l'horizontale déplace la bande et la position est enregistrée
  par écran.
- **Le raccourci par défaut `Ctrl+Alt+V`** affiche/masque (et lance l'app si elle ne tourne pas).
- **Quitter pour de bon** se fait par le menu → *Quitter*.

> Les raccourcis commençant par `Super` sont souvent interceptés par le système avant
> d'atteindre l'app. C'est pourquoi le défaut est `Ctrl+Alt+V` ; le changer tient en une ligne de config.

## Configuration

Linux : `~/.config/vigia/vigia.toml` · Windows : `%APPDATA%\vigia\vigia.toml`.
Le menu écrit dans ce fichier ; les modifications manuelles sont appliquées avec `vigia --reload`.

```toml
[overlay]
opacity = 0.82          # 0.40 à 1.00 — transparence du fond uniquement
size = "medium"         # small | medium | large
icon_style = "brand"    # brand | mono | alert
monitor = "primary"     # primary | secondary | all | "0", "1", ...
anchor = "top-right"    # top-left | top-center | top-right
                        # middle-left | middle-center | middle-right
                        # bottom-left | bottom-center | bottom-right
island = false          # true : ancré en haut comme une fine bande (mode îlot)
island_anchor = "top-center" # bord-position : top|bottom-left|center|right, left|right-top|middle|bottom
always_on_top = true
show_system = false     # CPU / RAM / GPU
autostart = true
refresh_minutes = 5     # 1 à 60
max_providers = 4       # 1 à 8
hotkey = "<Control><Alt>v"
language = "auto"       # auto | pt | en | es | fr | de
alert_warn = 60         # icon_style = "alert" : ambre à partir d'ici
alert_critical = 80     # ... et rouge à partir d'ici
hide_providers = ""     # ids séparés par des virgules : "openai,gemini"
hide_system = ""        # "cpu,ram,gpu" pour masquer des éléments système

[overlay.metrics]       # quelle limite chaque fournisseur affiche (par défaut : la plus forte utilisation)
anthropic = "Weekly (7d)"
"opencode-go" = "Rolling (5h)"

[overlay.island_offsets] # décalage horizontal de l'îlot sur chaque écran
"HDMI-A-0" = -40
```

Pour choisir ce qui s'affiche, utilisez le menu **Éléments** (case à cocher par fournisseur et par
CPU/RAM/GPU) — le choix va dans `hide_providers` et `hide_system`. Les éléments masqués
restent listés dans le menu, on peut donc les ramener. Avec `icon_style =
"alert"`, les chiffres passent à l'ambre et au rouge selon `alert_warn` / `alert_critical`.

La table `[overlay.positions]` conserve le décalage de chaque écran (clé = nom
de l'écran) après un glissement — inutile d'y toucher. *Réinitialiser la position* dans le
menu efface ces valeurs et revient à l'ancrage choisi. En mode île, il en va de même
pour `[overlay.island_offsets]`, qui ne garde que le décalage horizontal.

## Thèmes

L'apparence suit le format [DESIGN.md](https://github.com/google-labs-code/design.md) : chaque thème est un fichier `.md` dont le front matter définit les couleurs (`surface`, `text-primary`, `state-ok`, `state-warning`, `state-critical`, `primary`, ...). Le thème par défaut est le [`DESIGN.md`](DESIGN.md) à la racine.

Thèmes inclus dans [`themes/`](themes/) : Midnight, Graphite, Light, Aurora, Sunset et Mono High Contrast (AAA). Choisissez via engrenage → **Thème**, ou utilisez **Automatique (système)** pour alterner entre sombre et clair selon le système. **Couleur d'accent…** (dans le même sous-menu) change la couleur principale de n'importe quel thème. Chaque chiffre reçoit une fine barre d'usage (menu **Barres de progression**), et en mode « Alerte d'usage » les valeurs critiques pulsent doucement (menu **Pulser en état critique**). Pour créer le vôtre, copiez un fichier de `themes/` vers `~/.config/vigia/themes/`, modifiez les couleurs et validez avec `npx @google/design.md lint <fichier>` ; il apparaît dans le menu.

## Langues

Le défaut est **Automatique** (suit la locale du système ; sous Windows, la langue de
l'interface). Pour en fixer une, utilisez le menu **Langue** ou `language = "en"`.
Disponibles : `pt`, `en`, `es`, `fr`, `de`.

## Ligne de commande

| Commande | Ce qu'elle fait |
|---|---|
| `vigia` | ouvre la pastille (affiche l'instance existante, s'il y en a une) |
| `vigia --show` | affiche, en lançant si nécessaire |
| `vigia --toggle` | affiche/masque (pratique pour un raccourci) |
| `vigia --reload` | relit la config sans redémarrer |
| `vigia --quit` | termine l'instance |
| `vigia --version` | affiche la version |

## Comment les données sont lues

- **Fournisseurs** : `ai-usagebar usage --json`, toutes les 5 minutes. Chaque pastille montre une
  limite de ce fournisseur : celle choisie dans *Quoi surveiller* ou, par défaut, la plus consommée.
- **CPU/RAM** : `psutil` si disponible ; sous Linux, `/proc/stat` et `/proc/meminfo` ; sous Windows, l'API du système.
- **GPU** : `gpu_busy_percent` de `sysfs` (Linux) ou `nvidia-smi` (s'il existe).

Rien ne quitte votre machine en dehors des appels que `ai-usagebar` effectue déjà.

## Structure

```
vigia            lanceur (Python)
vigia_qt.py      interface Qt — la même sur les deux systèmes
vigia_core.py    données, config, langues, thèmes, métriques
DESIGN.md        thème par défaut (format DESIGN.md)
themes/          thèmes supplémentaires : Midnight, Graphite, Light, Aurora, Sunset, Mono HC
icons/           marques des fournisseurs (SVG)
assets/          icône de l'app et engrenage
tests/           tests du noyau et smoke test Qt
install.sh       installateur Linux
install.ps1      installateur Windows
```

## Limitations connues

- **Wayland** : le raccourci global et le positionnement libre des fenêtres sont restreints par le
  compositeur. La pastille apparaît, mais le `hotkey` peut ne pas fonctionner — utilisez le raccourci
  du bureau lui-même en appelant `vigia --toggle`.
- **Windows 11** : le code est le même et la CI exécute les tests sur `windows-latest`,
  mais la validation visuelle a été faite sous Linux/X11. Si quelque chose est mal placé,
  ouvrez une issue avec une capture d'écran.
- Le GPU dépend du pilote exposant `gpu_busy_percent` (Linux) ou de la présence de
  `nvidia-smi` ; sans cela, l'élément est omis (au lieu d'afficher zéro).
- Les traductions en espagnol, français et allemand sont une première passe — les corrections sont les bienvenues.

## Un problème ?

- **Qt ne s'ouvre pas (Linux)** : `libxcb-cursor0` manque → `sudo apt install libxcb-cursor0`
  (Fedora : `xcb-util-cursor` ; Arch : `xcb-util-cursor`). L'installateur essaie de le résoudre.
- **Rien n'apparaît dans la pastille** : lancez `ai-usagebar usage --json` et vérifiez s'il y a des données.
- **Pas de raccourci sous Wayland** : voir *Limitations connues*.
- **Journal** : Linux `~/.cache/vigia/vigia.log` · Windows `%LOCALAPPDATA%\vigia\vigia.log`.

## Désinstallation

Linux :

```bash
vigia --quit
rm -f  ~/.local/bin/vigia
rm -rf ~/.local/share/vigia ~/.config/vigia
rm -f  ~/.local/share/applications/vigia.desktop ~/.config/autostart/vigia.desktop
rm -f  ~/.local/share/icons/hicolor/scalable/apps/vigia.svg
```

Windows (PowerShell) :

```powershell
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\vigia"
Remove-Item -Recurse -Force "$env:APPDATA\vigia"
Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\VigIA.lnk"
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name VigIA
```

## Crédits

- Données de quota : [ai-usagebar](https://github.com/akitaonrails/ai-usagebar).
- Les icônes des fournisseurs sont des marques de leurs propriétaires respectifs, utilisées ici uniquement
  à des fins d'identification, et proviennent du paquet d'`ai-usagebar`/Omarchy.

## Licence

MIT — voir [LICENSE](LICENSE).
