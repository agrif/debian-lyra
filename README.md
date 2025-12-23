Debian for Luckfox Lyra Boards
==============================

[![Build](https://github.com/agrif/debian-lyra/actions/workflows/build.yaml/badge.svg)](https://github.com/agrif/debian-lyra/actions/workflows/build.yaml)

Get required sources:

    git submodule init
    git submodule update

Install dependencies:

    sudo apt-get install bmaptool build-essential debhelper debos \
        device-tree-compiler gcc-arm-none-eabi lz4 python3-pyelftools \
        xz-utils

Build image:

    ./build.sh all

Write image to SD card:

    bmaptool copy --removable-device build/luckfox-lyra-trixie-sd.img.xz \
        /dev/sdcard

Connect over serial port. Username is `lyra`, password is
`luckfox`. You will be prompted to change the default password after
login.
