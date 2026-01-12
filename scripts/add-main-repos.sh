#!/bin/sh

CODENAME=$1
[ "$CODENAME" ] || exit 1

rm -f /etc/apt/sources.list

cat > /etc/apt/sources.list.d/debian.sources <<EOF
# $CODENAME main and updates repo
Types: deb deb-src
URIs: https://deb.debian.org/debian/
Suites: $CODENAME $CODENAME-updates
Components: main contrib non-free non-free-firmware
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg

# $CODENAME security repo
Types: deb deb-src
URIs: https://security.debian.org/debian-security
Suites: $CODENAME-security
Components: main contrib non-free non-free-firmware
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg
EOF
