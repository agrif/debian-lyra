Debian for Luckfox Lyra
=======================

Install dependencies:

    sudo apt-get install bmaptool debos xz-utils
    
Build image:

    debos debos.yaml
    
Write image to SD card:

    bmaptool copy --removable-device debian-trixie-luckfox-lyra-sd.img.xz \
        /dev/sdcard
