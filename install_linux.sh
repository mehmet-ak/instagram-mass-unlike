#!/usr/bin/env sh
# Adds "Instagram Mass Unlike" to your application menu, with its icon (Linux).
#
# Put this script, InstagramMassUnlike-LinuxGUI and icon.png in the same folder, then run:
#     sh install_linux.sh
# The icon is referenced by its full path, so it shows up without refreshing any icon cache.
# Run it again after moving the folder. To remove the menu entry, delete
# ~/.local/share/applications/instagram-mass-unlike.desktop

set -eu

DIR="$(cd "$(dirname "$0")" && pwd)"
BINARY="$DIR/InstagramMassUnlike-LinuxGUI"
ICON_SOURCE="$DIR/icon.png"

if [ ! -f "$BINARY" ]; then
    echo "Cannot find $BINARY" >&2
    exit 1
fi
if [ ! -f "$ICON_SOURCE" ]; then
    echo "Cannot find $ICON_SOURCE" >&2
    exit 1
fi

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APPLICATIONS_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/256x256/apps"

chmod +x "$BINARY"
mkdir -p "$APPLICATIONS_DIR" "$ICON_DIR"
ICON_TARGET="$ICON_DIR/instagram-mass-unlike.png"
cp "$ICON_SOURCE" "$ICON_TARGET"

cat > "$APPLICATIONS_DIR/instagram-mass-unlike.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Instagram Mass Unlike
Comment=Remove your Instagram likes in bulk
Exec="$BINARY"
Icon=$ICON_TARGET
Terminal=false
Categories=Utility;
StartupWMClass=InstagramMassUnlike
EOF

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi

echo "Done. Look for \"Instagram Mass Unlike\" in your application menu."
echo "If the menu still shows no icon, log out and back in once."
