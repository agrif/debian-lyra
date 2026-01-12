#!/bin/sh

cd /opt/lyra-packages

apt-ftparchive packages . > Packages
apt-ftparchive contents . > Contents
apt-ftparchive release . > Release

cat > /etc/apt/sources.list.d/lyra-local.sources <<EOF
# local repository for lyra-specific packages
Types: deb
URIs: file:/opt/lyra-packages
Suites: ./
Trusted: yes
EOF
