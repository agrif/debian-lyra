Debian for Luckfox Lyra Boards
==============================

[![Build](https://github.com/agrif/debian-lyra/actions/workflows/build.yaml/badge.svg)](https://github.com/agrif/debian-lyra/actions/workflows/build.yaml)

Build
-----

Get required sources:

    git submodule init
    git submodule update

Install dependencies:

    sudo apt-get install bmaptool build-essential debhelper debos \
        device-tree-compiler devscripts gcc-arm-none-eabi lz4 \
        python3-pyelftools xz-utils

Build image:

    ./build.sh all

Install
-------

Write image to SD card:

    bmaptool copy --removable-device build/luckfox-lyra-trixie-sd.img.xz \
        /dev/sdcard

Connect
-------

Username is `lyra`, password is `luckfox`. You will be prompted to
change the default password after login.

Connect via:

 * **Serial Port** on UART0. See the board pinout for which pins to use.\

 * **USB Ethernet** at `192.168.123.100/24`. Configure your local IP
   to another in the `192.168.123.xxx` subnet, and use SSH to connect.

 * **USB Ethernet using DHCP**. If there is a DHCP server connected to
   the board over USB, it will configure itself automatically. You can
   do this in Linux by (for example) bridging the USB interface with
   your primary interface.
