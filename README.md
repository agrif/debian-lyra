Debian for Luckfox Lyra Boards
==============================

Get required sources:

    git submodule init
    git submodule update

Install dependencies:

    sudo apt-get install bmaptool build-essential debos device-tree-compiler \
        gcc-arm-none-eabi xz-utils

Build image:

    ./build.sh

Write image to SD card:

    bmaptool copy --removable-device build/luckfox-lyra-trixie-sd.img.xz \
        /dev/sdcard

Connect over serial port. Username is `lyra`, password is
`luckfox`. You will be prompted to change the default password after
login.
