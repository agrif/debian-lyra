#!/usr/bin/bash
set -e
R=$(realpath $(dirname "$0"))
cd $R

# set here because multiple things need to agree on this
CODENAME=trixie

JOBS=${JOBS:=$(nproc --all)}
mkdir -p build/parts/
mkdir -p build/packages/
mkdir -p build/source-packages/

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

(
    cd sources/u-boot/

    # prepare u-boot
    make mrproper
    cp $R/configs/u-boot/rk3506_luckfox_defconfig .config
    cp $R/configs/u-boot/rk3506-luckfox.dts{,i} arch/arm/dts/
    cp $R/configs/u-boot/evb_rk3506.h include/configs/

    # build u-boot
    make CROSS_COMPILE=arm-none-eabi- KCFLAGS=-Wno-error olddefconfig
    make -j${JOBS} CROSS_COMPILE=arm-none-eabi- KCFLAGS=-Wno-error

    # grab op-tee from rkbin, and create the u-boot FIT
    cp ../rkbin/bin/rk35/rk3506_tee_v2.10.bin ./tee.bin
    make -j${JOBS} CROSS_COMPILE=arm-none-eabi- KCFLAGS=-Wno-error u-boot.itb

    # fix up op-tee load address
    sed -i 's/entry = <0x8400000>;/entry = <0x1000>;/' u-boot.its
    sed -i 's/load = <0x8400000>;/load = <0x1000>;/' u-boot.its
    ./tools/mkimage -f u-boot.its -E u-boot.itb

    cp u-boot.itb $R/build/parts/
)

#
# Kernel
#

(
    cd sources/kernel/

    # prepare kernel
    make mrproper
    cp $R/configs/kernel/rk3506_luckfox_defconfig .config
    cp $R/configs/kernel/*.dts{,i} arch/arm/boot/dts/rockchip/
    cp $R/configs/kernel/Makefile.dtb arch/arm/boot/dts/rockchip/Makefile

    # temporarily stage dts so deb-pkg picks it up
    git add arch/arm/boot/dts/rockchip/*.dts{,i}

    # build kernel
    make ARCH=arm CROSS_COMPILE=arm-none-eabi- olddefconfig
    make ARCH=arm CROSS_COMPILE=arm-none-eabi- -j${JOBS} \
         KDEB_SOURCENAME=linux-lyra KDEB_CHANGELOG_DIST=$CODENAME deb-pkg
    rm linux.tar.gz
    mv ../linux-*.deb $R/build/packages/
    mv ../linux-lyra* $R/build/source-packages/
    cp arch/arm/boot/dts/rockchip/rk3506g-luckfox-lyra.dtb $R/build/parts/

    # unstage dts
    git restore --staged arch/arm/boot/dts/rockchip/*.dts{,i}
)

#
# Debos
#

debos --artifactdir=build/ -t codename:$CODENAME root-fs.yaml
debos --artifactdir=build/ -t codename:$CODENAME sd-image.yaml
