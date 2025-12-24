#!/bin/sh

cat >> /etc/fstab <<EOF

# systemd needs at least 16MiB free here
tmpfs	/run	tmpfs	rw,nosuid,nodev,noexec,relatime,size=20%,mode=755	0	0

EOF
