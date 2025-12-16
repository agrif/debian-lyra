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
    sed -i 's/entry = <0x8400000>;/entry = <0x1000>;/' u-boot.its
    sed -i 's/load = <0x8400000>;/load = <0x1000>;/' u-boot.its
    ./tools/mkimage -f u-boot.its -E u-boot.itb

    mv u-boot.itb $R/build/parts/
)

#
# Kernel
#

(
    cd sources/kernel/

    # build kernel
    make mrproper
    cp $R/configs/kernel/rk3506_luckfox_defconfig .config
    make ARCH=arm CROSS_COMPILE=arm-none-eabi- olddefconfig
    make ARCH=arm CROSS_COMPILE=arm-none-eabi- -j${JOBS}
    cp arch/arm/boot/zImage $R/build/parts/

    # build kernel packages
    rm .version
    make ARCH=arm CROSS_COMPILE=arm-none-eabi- \
         KDEB_SOURCENAME=linux-lyra KDEB_CHANGELOG_DIST=$CODENAME deb-pkg
    rm linux.tar.gz
    mv ../linux-*.deb $R/build/packages/
    mv ../linux-lyra* $R/build/source-packages/

    # build device tree
    cpp -nostdinc -undef -x assembler-with-cpp \
        -I include/ -I arch/arm/boot/dts/rockchip/ \
        $R/configs/kernel/rk3506g-luckfox-lyra.dts |
        dtc -O dtb -o $R/build/parts/device-tree.dtb
)

#
# Debos
#

debos --artifactdir=build/ -t codename:$CODENAME root-fs.yaml
debos --artifactdir=build/ -t codename:$CODENAME sd-image.yaml
