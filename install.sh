#!/usr/bin/env bash
# VigIA installer — copies the app, icons and a desktop entry into ~/.local.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${PREFIX:-$HOME/.local}"
BIN="$PREFIX/bin"
DATA="$PREFIX/share/vigia"
APPS="$PREFIX/share/applications"
THEME="$PREFIX/share/icons/hicolor"

say() { printf '%s\n' "$*"; }

command -v python3 >/dev/null 2>&1 || { say "python3 não encontrado."; exit 1; }

python3 - <<'EOF' || { echo "Faltam dependências do Python/GTK. Veja a seção Requisitos do README."; exit 1; }
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: F401
import tomllib  # noqa: F401
EOF

install -Dm755 "$SRC/vigia" "$BIN/vigia"
mkdir -p "$DATA/icons"
cp "$SRC"/icons/*.svg "$DATA/icons/"

install -Dm644 "$SRC/assets/vigia.svg" "$THEME/scalable/apps/vigia.svg"

mkdir -p "$APPS"
cat > "$APPS/vigia.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=VigIA
Comment=AI usage and system metrics at a glance
GenericName=AI Usage Monitor
Exec="$BIN/vigia" --show
Icon=vigia
Terminal=false
Categories=Utility;
StartupNotify=false
Keywords=AI;Usage;Claude;Codex;OpenCode;Overlay;Pill;VigIA;
Actions=Toggle;

[Desktop Action Toggle]
Name=Mostrar / esconder
Exec="$BIN/vigia" --toggle
EOF

gtk-update-icon-cache -f -t "$THEME" >/dev/null 2>&1 || true
update-desktop-database "$APPS" >/dev/null 2>&1 || true

say ""
say "VigIA instalado em $BIN/vigia"
say "Abra com: vigia"
say "Ou procure \"VigIA\" no menu de aplicativos."
say ""
say "Sem atalho global? Instale gir1.2-keybinder-3.0 e reinicie o app."
say "Sem dados? Instale o CLI ai-usagebar: https://github.com/akitaonrails/ai-usagebar"
