Debian for Luckfox Lyra
=======================

Get required sources:

    git submodule init
    git submodule update

Install dependencies:

    sudo apt-get install gcc-arm-none-eabi build-essential bmaptool \
        debos xz-utils

Build image:

    ./build.sh

Write image to SD card:

    bmaptool copy --removable-device \
        build/debian-trixie-luckfox-lyra-sd.img.xz \
        /dev/sdcard
