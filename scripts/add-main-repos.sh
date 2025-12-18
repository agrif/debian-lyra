#!/bin/sh

CODENAME=$1
[ "$CODENAME" ] || exit 1

cat > /etc/apt/sources.list <<EOF
# $CODENAME main repo
deb https://deb.debian.org/debian/ $CODENAME main contrib non-free non-free-firmware
deb-src https://deb.debian.org/debian/ $CODENAME main contrib non-free non-free-firmware

# $CODENAME security repo
deb https://security.debian.org/debian-security $CODENAME-security main contrib non-free non-free-firmware
deb-src https://security.debian.org/debian-security $CODENAME-security main contrib non-free non-free-firmware

# $CODENAME updates repo
deb https://deb.debian.org/debian/ $CODENAME-updates main contrib non-free non-free-firmware
deb-src https://deb.debian.org/debian/ $CODENAME-updates main contrib non-free non-free-firmware
EOF
