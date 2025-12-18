#!/bin/sh

cd /opt/lyra-packages

apt-ftparchive packages . > Packages
apt-ftparchive contents . > Contents
apt-ftparchive release . > Release

cat > /etc/apt/sources.list.d/lyra-local.list <<EOF
# local repository for lyra-specific packages
deb [trusted=yes] file:/opt/lyra-packages/ ./
EOF
