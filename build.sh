#!/usr/bin/bash
set -e
R=$(realpath $(dirname "$0"))
cd $R

JOBS=${JOBS:=$(nproc --all)}
mkdir -p build/parts/

#
# idblock
#

(
    cd sources/rkbin/

    ./tools/boot_merger RKBOOT/RK3506MINIALL.ini
    rm rk3506_spl_loader_v1.06.111.bin
    mv rk3506_idblock_v1.06.111.img $R/build/parts/idblock.img
)

#
# U-Boot
#

cp configs/u-boot/*_defconfig sources/u-boot/configs/
cp configs/u-boot/*.dts{,i} sources/u-boot/arch/arm/dts/

(
    cd sources/u-boot/

    # build u-boot
    make mrproper
    make rk3506_luckfox_defconfig
    make -j${JOBS} CROSS_COMPILE=arm-none-eabi- KCFLAGS=-Wno-error

    # grab op-tee from rkbin, and create the u-boot FIT
    cp ../rkbin/bin/rk35/rk3506_tee_v2.10.bin ./tee.bin
    make -j${JOBS} CROSS_COMPILE=arm-none-eabi- KCFLAGS=-Wno-error u-boot.itb

    # fix up op-tee load address
    fdtput -t x u-boot.itb /images/optee entry 0x1000
    fdtput -t x u-boot.itb /images/optee load 0x1000

    mv u-boot.itb $R/build/parts/
)

#
# Debos
#

debos --artifactdir=build/ debos.yaml
