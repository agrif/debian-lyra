Remote Processor Driver for RK3506 M0
=====================================

This is a driver for the M0 core on the RK3506 SoC.

To build on the device itself:

    make -C /lib/modules/$(uname -r)/build M=$PWD

To cross-compile using a kernel built for RK3506:

    make -C path/to/kernel ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- M=$PWD
