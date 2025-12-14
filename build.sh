#!/usr/bin/bash
set -e
cd "$(dirname "$0")"

#
# U-Boot
#

cp configs/u-boot/*_defconfig sources/u-boot/configs/
cp configs/u-boot/*.dts{,i} sources/u-boot/arch/arm/dts/

(
    cd sources/u-boot/
    KCFLAGS=-Wno-error ./make.sh CROSS_COMPILE=arm-none-eabi- rk3506_luckfox
)

#
# Debos
#

mkdir -p build/
debos --artifactdir=build/ debos.yaml
