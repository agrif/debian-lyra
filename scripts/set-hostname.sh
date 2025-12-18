#!/bin/sh

HOSTNAME=$1
[ "$HOSTNAME" ] || exit 1

echo "$HOSTNAME" > /etc/hostname

cat > /etc/hosts <<EOF
127.0.0.1	localhost
127.0.1.1	$HOSTNAME
# The following lines are desirable for IPv6 capable hosts
::1     localhost ip6-localhost ip6-loopback
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
EOF
