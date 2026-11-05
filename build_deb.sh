#!/usr/bin/env sh
# Builds ONE installable package for Debian, Ubuntu, Linux Mint and friends.
# Double-clicking the resulting .deb installs the app, adds it to the application
# menu WITH its icon, and lets the user uninstall it from the Software Manager.
#
# Usage (from the repository root, after PyInstaller has built the executable):
#     sh build_deb.sh [version]        e.g.  sh build_deb.sh 1.1.0
set -eu

VERSION="${1:-1.1.0}"
PACKAGE="instagram-mass-unlike"
BINARY="dist/InstagramMassUnlike-LinuxGUI"
ICON="assets/icon.png"
ARCH="$(dpkg --print-architecture)"
STAGE="build/deb/${PACKAGE}_${VERSION}_${ARCH}"
OUTPUT="dist/${PACKAGE}_${VERSION}_${ARCH}.deb"

if [ ! -f "$BINARY" ]; then
    echo "Cannot find $BINARY - build it with PyInstaller first (see build_linux.sh)." >&2
    exit 1
fi

rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" \
         "$STAGE/usr/bin" \
         "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/icons/hicolor/256x256/apps" \
         "$STAGE/usr/share/doc/$PACKAGE"

install -m 755 "$BINARY" "$STAGE/usr/bin/$PACKAGE"
install -m 644 "$ICON" "$STAGE/usr/share/icons/hicolor/256x256/apps/$PACKAGE.png"

cat > "$STAGE/usr/share/applications/$PACKAGE.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Instagram Mass Unlike
Comment=Remove your Instagram likes in bulk
Exec=$PACKAGE
Icon=$PACKAGE
Terminal=false
Categories=Utility;
StartupWMClass=InstagramMassUnlike
DESKTOP
chmod 644 "$STAGE/usr/share/applications/$PACKAGE.desktop"

cat > "$STAGE/usr/share/doc/$PACKAGE/copyright" <<COPYRIGHT
Instagram Mass Unlike Bot
Upstream: https://github.com/mehmet-ak/instagram-mass-unlike
Copyright (C) 2026 mehmet-ak

License: GPL-3+
 This program is free software: you can redistribute it and/or modify it under
 the terms of the GNU General Public License as published by the Free Software
 Foundation, either version 3 of the License, or (at your option) any later
 version.
 .
 On Debian systems, the full text of the GNU General Public License version 3
 can be found in /usr/share/common-licenses/GPL-3.
COPYRIGHT
chmod 644 "$STAGE/usr/share/doc/$PACKAGE/copyright"

INSTALLED_SIZE="$(du -sk "$STAGE/usr" | cut -f1)"
cat > "$STAGE/DEBIAN/control" <<CONTROL
Package: $PACKAGE
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Maintainer: mehmet-ak <mehmet-ak@users.noreply.github.com>
Installed-Size: $INSTALLED_SIZE
Recommends: google-chrome-stable | chromium | chromium-browser
Homepage: https://github.com/mehmet-ak/instagram-mass-unlike
Description: Remove your Instagram likes in bulk
 A desktop wizard that removes your likes from Instagram posts and Reels,
 using the data export Instagram provides and a Chrome window.
 Requires Google Chrome. Use at your own risk. Not affiliated with
 Instagram or Meta.
CONTROL

mkdir -p dist
dpkg-deb --build --root-owner-group "$STAGE" "$OUTPUT" >/dev/null
echo "Built $OUTPUT"
