#!/usr/bin/env bash
# VigIA installer — Linux. Creates a private venv with PySide6 and installs the app.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${PREFIX:-$HOME/.local}"
DATA="$PREFIX/share/vigia"
BIN="$PREFIX/bin"
APPS="$PREFIX/share/applications"
THEME="$PREFIX/share/icons/hicolor"

say() { printf '%s\n' "$*"; }
die() { printf 'erro: %s\n' "$*" >&2; exit 1; }

command -v python3 >/dev/null 2>&1 || die "python3 não encontrado"
python3 - <<'EOF' || die "precisa de Python 3.11 ou mais novo"
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
EOF

if ! python3 -c "import venv" 2>/dev/null; then
    die "módulo venv ausente. No Debian/Ubuntu/Mint: sudo apt install python3-venv"
fi

# Qt 6 (xcb) needs libxcb-cursor0. Try the distro package; on Debian-like systems
# fall back to extracting the tiny library next to the app (no root needed).
has_xcb_cursor() {
    ldconfig -p 2>/dev/null | grep -q libxcb-cursor && return 0
    find /usr/lib /lib -name 'libxcb-cursor.so*' 2>/dev/null | grep -q . && return 0
    [ -e "$DATA/lib/libxcb-cursor.so.0" ]
}

install_xcb_cursor() {
    if has_xcb_cursor; then return 0; fi
    say "Falta libxcb-cursor0 (exigida pelo Qt 6)."
    if command -v apt-get >/dev/null 2>&1 && command -v dpkg-deb >/dev/null 2>&1; then
        tmp="$(mktemp -d)"
        if (cd "$tmp" && apt-get download libxcb-cursor0 >/dev/null 2>&1 && dpkg-deb -x ./*.deb extracted); then
            mkdir -p "$DATA/lib"
            find "$tmp/extracted" -name 'libxcb-cursor.so*' -exec cp -a {} "$DATA/lib/" \;
            say "Biblioteca incluída em $DATA/lib (sem precisar de root)."
            rm -rf "$tmp"
            return 0
        fi
        rm -rf "$tmp"
    fi
    say "Instale o pacote e rode de novo:"
    say "  Debian/Ubuntu/Mint : sudo apt install libxcb-cursor0"
    say "  Fedora             : sudo dnf install xcb-util-cursor"
    say "  Arch               : sudo pacman -S xcb-util-cursor"
    exit 1
}

install_xcb_cursor

install -d "$DATA" "$BIN" "$APPS" "$THEME/scalable/apps" "$DATA/icons"
install -m644 "$SRC/vigia_qt.py" "$SRC/vigia_core.py" "$SRC/vigia" "$DATA/"
cp "$SRC"/icons/*.svg "$DATA/icons/"
install -d "$DATA/assets"
cp "$SRC"/assets/*.svg "$DATA/assets/"
install -m644 "$SRC/assets/vigia.svg" "$THEME/scalable/apps/vigia.svg"

if [ ! -x "$DATA/venv/bin/python" ]; then
    say "Criando ambiente Python em $DATA/venv ..."
    rm -rf "$DATA/venv"
    if command -v uv >/dev/null 2>&1; then
        uv venv "$DATA/venv"
    else
        python3 -m venv "$DATA/venv" || die "não consegui criar o venv. Instale python3-venv (Debian/Ubuntu/Mint) ou uv."
    fi
fi

if ! "$DATA/venv/bin/python" -c "import PySide6" 2>/dev/null; then
    say "Instalando PySide6 (≈82 MB de download; ~245 MB instalado) ..."
    if command -v uv >/dev/null 2>&1; then
        uv pip install --python "$DATA/venv/bin/python" PySide6-Essentials psutil
    else
        "$DATA/venv/bin/python" -m pip install --upgrade pip >/dev/null
        "$DATA/venv/bin/python" -m pip install PySide6-Essentials psutil
    fi
fi

cat > "$BIN/vigia" <<EOF
#!/bin/sh
exec "$DATA/venv/bin/python" "$DATA/vigia" "\$@"
EOF
chmod +x "$BIN/vigia"

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
say "Sem dados? Instale o CLI ai-usagebar: https://github.com/akitaonrails/ai-usagebar"
