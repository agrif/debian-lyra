#!/bin/sh

DEVICETREE=$1
[ "$DEVICETREE" ] || exit 1

mkdir -p /etc/u-boot-menu/conf.d/

cat > /etc/u-boot-menu/conf.d/50-lyra.conf <<EOF
U_BOOT_PARAMETERS="earlycon=uart8250,mmio32,0xff0a0000 console=tty1 console=ttyS0,1500000 rootwait ro"
U_BOOT_TIMEOUT="20"
U_BOOT_FDT="$DEVICETREE"
U_BOOT_SYNC_DTBS="true"
EOF
