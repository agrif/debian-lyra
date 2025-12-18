#!/usr/bin/bash
set -e

# Do Not Become That Which You Despise
# (try to keep this readable as an instruction list, as well as a script)

# configuration
CODENAME=${CODENAME:=trixie}
JOBS=${JOBS:=$(nproc --all)}

# paths: $R is repository root, $B is build directory
R=$(realpath "$(dirname "$0")")
B=$(realpath "${B:=$R/build}")
cd $R

#
# Help
#

build_help() {
    cat <<EOF
Usage: $0 <part> [part ...]

where <part> is one of:

    idblock   build the Rockchip idblock
    uboot     build U-Boot
    kernel    build the Linux kernel
    root      build the root filesystem

    sdimage   combine idblock, uboot, kernel, and root into SD image

    all       run everything

The following environment variables control the build:

    B         output directory (default: build)
    CODENAME  Debian distribution to build
    JOBS      parallel jobs when compiling (default: `nproc --all`)

EOF
    exit 0
}

#
# Do everything!
#

build_all() {
    build_idblock
    build_uboot
    build_kernel
    build_root
    build_sdimage
}

#
# idblock
#

build_idblock() (
    cd $R/sources/rkbin/
    mkdir -p $B/parts/

    ./tools/boot_merger RKBOOT/RK3506MINIALL.ini
    rm rk3506_spl_loader_v1.06.111.bin
    mv rk3506_idblock_v1.06.111.img $B/parts/idblock.img
)

#
# U-Boot
#

build_uboot() (
    cd $R/sources/u-boot/
    mkdir -p $B/parts/

    # prepare u-boot
    make mrproper
    cp $R/configs/u-boot/rk3506_luckfox_defconfig .config
    cp $R/configs/u-boot/rk3506-luckfox.dts{,i} arch/arm/dts/
    cp $R/configs/u-boot/evb_rk3506.h include/configs/

    # build u-boot
    make CROSS_COMPILE=arm-none-eabi- KCFLAGS=-Wno-error olddefconfig
    make -j${JOBS} CROSS_COMPILE=arm-none-eabi- KCFLAGS=-Wno-error

    # grab op-tee from rkbin, and create the u-boot FIT
    cp $R/sources/rkbin/bin/rk35/rk3506_tee_v2.10.bin ./tee.bin
    make -j${JOBS} CROSS_COMPILE=arm-none-eabi- KCFLAGS=-Wno-error u-boot.itb

    # fix up op-tee load address
    sed -i 's/entry = <0x8400000>;/entry = <0x1000>;/' u-boot.its
    sed -i 's/load = <0x8400000>;/load = <0x1000>;/' u-boot.its
    ./tools/mkimage -f u-boot.its -E u-boot.itb

    cp u-boot.itb $B/parts/
)

#
# Kernel
#

build_kernel() (
    cd $R/sources/kernel/
    mkdir -p $B/packages/ $B/source-packages/

    # prepare kernel
    make mrproper
    cp $R/configs/kernel/rk3506_luckfox_defconfig .config
    cp $R/configs/kernel/*.dts{,i} arch/arm/boot/dts/rockchip/
    cp $R/configs/kernel/Makefile.dtb arch/arm/boot/dts/rockchip/Makefile

    # temporarily stage dts so deb-pkg picks it up
    git add arch/arm/boot/dts/rockchip/*.dts{,i}

    # build kernel
    echo "0" > .version # debian-revision minus 1 (e.g.. "0" yields 6.6.89-1)
    make ARCH=arm CROSS_COMPILE=arm-none-eabi- olddefconfig
    make ARCH=arm CROSS_COMPILE=arm-none-eabi- -j${JOBS} \
         EXTRAVERSION=-lyra LOCALVERSION= \
         KDEB_SOURCENAME=linux-lyra KDEB_CHANGELOG_DIST=$CODENAME deb-pkg
    rm linux.tar.gz
    mv ../linux-*.deb $B/packages/
    mv ../linux-lyra* $B/source-packages/

    # unstage dts
    git restore --staged arch/arm/boot/dts/rockchip/*.dts{,i}
)

#
# Root Filesystem
#

build_root() (
    cd $R
    mkdir -p $B/parts
    debos --artifactdir=$B -t codename:$CODENAME root-fs.yaml
)

#
# SD Card Image
#

build_sdimage() (
    cd $R
    mkdir -p $B
    debos --artifactdir=$B -t codename:$CODENAME sd-image.yaml
)

#
# Main program, runs build_$ARG for each $ARG
#

if [ $# -eq 0 ]; then
    build_help
    exit 0
fi

while [ $# -gt 0 ]; do
    time build_$1
    shift
done
