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
    cat >&2 <<EOF
Usage: $0 <part> [part ...]

where <part> is one of:

    uboot     build U-Boot
    kernel    build the Linux kernel
    packages  build debian packages
    root      build the root filesystem

    image <board>
              combine uboot, kernel, packages, and root into SD image

    all       run everything

and <board> is one of:

EOF

    for board in $BOARDS; do
        get_board_config "$board"
        printf "    %-14s %s\n" "$board" "$BOARD_DESCRIPTION" >&2
    done

    cat >&2 <<EOF

    all            run given command for all boards

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
    build_image all
}

#
# per-board configuration
#

BOARDS="lyra lyra-plus lyra-ultra lyra-ultra-w lyra-zero-w lyra-pi-a lyra-pi-a-w lyra-pi-b lyra-pi-b-w"

get_board_config() {
    # set the following variables:
    # BOARD_DESCRIPTION: used in help text
    # BOARD_NAME: used in image filename
    # BOARD_UBOOT: the u-boot binary inside $B/parts/ to use
    # BOARD_DT: the device tree name to set for u-boot-menu
    # BOARD_PACKAGES: extra packages to install for this board (optional)
    case "$1" in
        lyra)
            BOARD_DESCRIPTION="Luckfox Lyra (A, B)"
            BOARD_NAME="luckfox-lyra"
            BOARD_UBOOT="u-boot-lyra-plus.bin"
            BOARD_DT="rk3506g-luckfox-lyra.dtb"
            ;;
        lyra-plus)
            BOARD_DESCRIPTION="Luckfox Lyra Plus (Ethernet)"
            BOARD_NAME="luckfox-lyra-plus"
            BOARD_UBOOT="u-boot-lyra-plus.bin"
            BOARD_DT="rk3506g-luckfox-lyra-plus.dtb"
            ;;
        lyra-ultra)
            BOARD_DESCRIPTION="Luckfox Lyra Ultra"
            BOARD_NAME="luckfox-lyra-ultra"
            BOARD_UBOOT="u-boot-lyra-ultra.bin"
            BOARD_DT="rk3506b-luckfox-lyra-ultra.dtb"
            ;;
        lyra-ultra-w)
            BOARD_DESCRIPTION="Luckfox Lyra Ultra W (Wireless)"
            BOARD_NAME="luckfox-lyra-ultra-w"
            BOARD_UBOOT="u-boot-lyra-ultra.bin"
            BOARD_DT="rk3506b-luckfox-lyra-ultra-w.dtb"
            BOARD_PACKAGES="[linux-headers-lyra, aic8800-usb-dkms]"
            ;;
        lyra-zero-w)
            BOARD_DESCRIPTION="Luckfox Lyra Zero W (Wireless)"
            BOARD_NAME="luckfox-lyra-zero-w"
            BOARD_UBOOT="u-boot-lyra-zero-w.bin"
            BOARD_DT="rk3506b-luckfox-lyra-zero-w.dtb"
            BOARD_PACKAGES="[linux-headers-lyra, aic8800-usb-dkms]"
            ;;
        lyra-pi-a)
            BOARD_DESCRIPTION="Luckfox Lyra Pi A (eMMC)"
            BOARD_NAME="luckfox-lyra-pi-a"
            BOARD_UBOOT="u-boot-lyra-pi.bin"
            BOARD_DT="rk3506b-luckfox-lyra-pi.dtb"
            ;;
        lyra-pi-a-w)
            BOARD_DESCRIPTION="Luckfox Lyra Pi A W (eMMC, Wireless)"
            BOARD_NAME="luckfox-lyra-pi-a-w"
            BOARD_UBOOT="u-boot-lyra-pi.bin"
            BOARD_DT="rk3506b-luckfox-lyra-pi-w.dtb"
            BOARD_PACKAGES="[linux-headers-lyra, aic8800-usb-dkms]"
            ;;
        lyra-pi-b)
            BOARD_DESCRIPTION="Luckfox Lyra Pi B (SD)"
            BOARD_NAME="luckfox-lyra-pi-b"
            BOARD_UBOOT="u-boot-lyra-pi.bin"
            BOARD_DT="rk3506b-luckfox-lyra-pi-sd.dtb"
            ;;
        lyra-pi-b-w)
            BOARD_DESCRIPTION="Luckfox Lyra Pi B W (SD, Wireless)"
            BOARD_NAME="luckfox-lyra-pi-b-w"
            BOARD_UBOOT="u-boot-lyra-pi.bin"
            BOARD_DT="rk3506b-luckfox-lyra-pi-w-sd.dtb"
            BOARD_PACKAGES="[linux-headers-lyra, aic8800-usb-dkms]"
            ;;

        # board name not matched
        *)
            if [ -z "$1" ]; then
                printf "ERROR: no board name given\n" >&2
            else
                printf "ERROR: bad board name: %s\n" "$1" >&2
            fi
            exit 1
    esac
}

#
# Helpers
#

patch_idempotent() {
    # applies a patch (like `patch`) but skips it if already applied
    # uses 0 fuzziness and doesn't leave other files laying around
    patch -t -F0 -R -N --dry-run "$@" > /dev/null \
        || patch -t -F0 -N -r- --no-backup-if-mismatch "$@"
}

#
# U-Boot
#

build_uboot() (
    cd $R/sources/u-boot/
    mkdir -p $B/parts/

    # prepare u-boot
    make mrproper

    # we want to use this, but it seems to be desync'd right now
    # (it prompts for OPTEE_TZDRAM_SIZE at build time, always)
    #make CROSS-COMPILE=arm-linux-gnueabihf- luckfox-lyra-rk3506_defconfig

    # so instead, use the same config with the default values selected
    # (and all)
    cp $R/configs/u-boot/luckfox-lyra-rk3506_defconfig .config
    make CROSS_COMPILE=arm-linux-gnueabihf- olddefconfig

    # we build multiple u-boots for multiple device trees, to be able
    # to do fun things like usb boot or network boot.
    # (this *should* use different configs, once configs work)

    # build u-boot (lyra plus)
    ./scripts/config --set-str OF_LIST rk3506-luckfox-lyra-plus \
                     --set-str DEFAULT_DEVICE_TREE rk3506-luckfox-lyra-plus
    make -j${JOBS} CROSS_COMPILE=arm-linux-gnueabihf- \
         ROCKCHIP_TPL=../rkbin/bin/rk35/rk3506_ddr_750MHz_v1.06.bin \
         TEE=../rkbin/bin/rk35/rk3506_tee_v2.10.bin
    cp u-boot-rockchip.bin $B/parts/u-boot-lyra-plus.bin

    # build u-boot (lyra ultra)
    ./scripts/config --set-str OF_LIST rk3506b-luckfox-lyra-ultra \
                     --set-str DEFAULT_DEVICE_TREE rk3506b-luckfox-lyra-ultra
    make -j${JOBS} CROSS_COMPILE=arm-linux-gnueabihf- \
         ROCKCHIP_TPL=../rkbin/bin/rk35/rk3506b_ddr_750MHz_v1.06.bin \
         TEE=../rkbin/bin/rk35/rk3506_tee_v2.10.bin
    cp u-boot-rockchip.bin $B/parts/u-boot-lyra-ultra.bin

    # build u-boot (lyra zero w)
    ./scripts/config --set-str OF_LIST rk3506b-luckfox-lyra-zero-w \
                     --set-str DEFAULT_DEVICE_TREE rk3506b-luckfox-lyra-zero-w
    make -j${JOBS} CROSS_COMPILE=arm-linux-gnueabihf- \
         ROCKCHIP_TPL=../rkbin/bin/rk35/rk3506b_ddr_750MHz_v1.06.bin \
         TEE=../rkbin/bin/rk35/rk3506_tee_v2.10.bin
    cp u-boot-rockchip.bin $B/parts/u-boot-lyra-zero-w.bin

    # build u-boot (lyra pi)
    ./scripts/config --set-str OF_LIST rk3506b-luckfox-lyra-pi \
                     --set-str DEFAULT_DEVICE_TREE rk3506b-luckfox-lyra-pi
    make -j${JOBS} CROSS_COMPILE=arm-linux-gnueabihf- \
         ROCKCHIP_TPL=../rkbin/bin/rk35/rk3506b_ddr_750MHz_v1.06.bin \
         TEE=../rkbin/bin/rk35/rk3506_tee_v2.10.bin
    cp u-boot-rockchip.bin $B/parts/u-boot-lyra-pi.bin
)

#
# Kernel
#

build_kernel() (
    cd $R/sources/kernel/
    mkdir -p $B/packages/ $B/source-packages/

    # prepare kernel
    make mrproper

    # copy in config, device trees, and add DTs to Makefile
    cp $R/configs/kernel/rk3506_luckfox_defconfig .config
    cp $R/configs/kernel/*.dts{,i} arch/arm/boot/dts/rockchip/
    cp $R/configs/kernel/Makefile.dtb arch/arm/boot/dts/rockchip/Makefile

    # make sure to build scripts/ for target during install
    # https://lore.kernel.org/all/20240727074526.1771247-1-masahiroy@kernel.org/
    # (and more recent fixes, rolled into one)
    patch_idempotent -p1 -i ../../configs/kernel/cross-compile-linux-headers.patch

    # fix DSI on one-lane displays, ported from lyra SDK
    patch_idempotent -p1 -i ../../configs/kernel/fix-one-lane-dsi.patch

    # temporarily stage dts so deb-pkg picks it up
    git add arch/arm/boot/dts/rockchip/*.dts{,i}

    # build kernel
    echo "0" > .version # debian-revision minus 1 (e.g.. "0" yields 6.6.89-1)
    make ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- olddefconfig
    make ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- -j${JOBS} \
         EXTRAVERSION=-lyra LOCALVERSION= \
         KDEB_SOURCENAME=linux-lyra KDEB_CHANGELOG_DIST=$CODENAME deb-pkg

    # move packages to $B
    rm linux.tar.gz
    rm ../linux-lyra_*.buildinfo
    mv ../linux-*.deb $B/packages/
    mv ../linux-lyra_*.{changes,debian.tar.gz,dsc,orig.tar.gz} $B/source-packages/

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
    rm ../lyra-usb-gadget_*.{build,buildinfo}
    mv ../lyra-usb-gadget_*.deb $B/packages/
    mv ../lyra-usb-gadget_*.{changes,dsc,tar.xz} $B/source-packages/

    cd $R/packages/lyra-overlays
    debuild -us -uc
    rm ../lyra-overlays_*.{build,buildinfo}
    mv ../lyra-overlays_*.deb $B/packages/
    mv ../lyra-overlays_*.{changes,dsc,tar.xz} $B/source-packages/

    cd $R/packages/aic8800
    debuild -us -uc
    rm ../aic8800_*.{build,buildinfo}
    mv ../aic8800-*.deb $B/packages/
    mv ../aic8800_*.{changes,debian.tar.xz,dsc} $B/source-packages/
    cp ../aic8800_*.orig.tar.xz $B/source-packages/

    cd $R/packages
    equivs-build -f linux-image-lyra.equivs
    rm linux-image-lyra_*.buildinfo
    mv linux-image-lyra_*.deb $B/packages/
    mv linux-image-lyra_*.{changes,dsc,tar.xz} $B/source-packages/

    cd $R/packages
    equivs-build -f linux-headers-lyra.equivs
    rm linux-headers-lyra_*.buildinfo
    mv linux-headers-lyra_*.deb $B/packages/
    mv linux-headers-lyra_*.{changes,dsc,tar.xz} $B/source-packages/
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

build_image() (
    cd $R
    mkdir -p $B

    # handle "all" special case
    if [ "$1" = "all" ]; then
        for board in $BOARDS; do
            build_image "$board"
        done
        return;
    fi

    get_board_config "$1"
    debos --artifactdir=$B \
          -t "codename:$CODENAME" \
          -t "board:$BOARD_NAME" \
          -t "uboot:$BOARD_UBOOT" \
          -t "devicetree:$BOARD_DT" \
          -t "packages:$BOARD_PACKAGES" \
          image.yaml
)

#
# Main program, runs build_$ARG for each $ARG
#

if [ $# -eq 0 ]; then
    build_help
    exit 0
fi

while [ $# -gt 0 ]; do
    case "$1" in
        image)
            # one argument
            time build_$1 "$2"
            shift
            shift
            ;;
        *)
            # no arguments
            time build_$1
            shift
            ;;
    esac
done
