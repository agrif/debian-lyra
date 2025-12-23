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

    uboot     build U-Boot
    kernel    build the Linux kernel
    packages  build debian packages
    root      build the root filesystem

    sdimage   combine uboot, kernel, packages, and root into SD image

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
    build_uboot
    build_kernel
    build_packages
    build_root
    build_sdimage
}

#
# U-Boot
#

build_uboot() (
    cd $R/sources/u-boot/
    mkdir -p $B/parts/

    # prepare u-boot
    make mrproper

    # build u-boot
    make CROSS-COMPILE=arm-none-eabi- luckfox-lyra_defconfig
    make -j${JOBS} CROSS_COMPILE=arm-none-eabi- \
         ROCKCHIP_TPL=../rkbin/bin/rk35/rk3506_ddr_750MHz_v1.06.bin \
         TEE=../rkbin/bin/rk35/rk3506_tee_ta_v1.10.bin

    cp u-boot-rockchip.bin $B/parts/
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
# Packages
#

build_packages() (
    mkdir -p $B/packages/ $B/source-packages/

    cd $R/packages/lyra-usb-gadget
    debuild -us -uc
    mv ../lyra-usb-gadget_*.deb $B/packages/
    mv ../lyra-usb-gadget_* $B/source-packages/
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
