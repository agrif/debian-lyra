/*
 * SPDX-License-Identifier:     GPL-2.0+
 *
 * Copyright (c) 2024 Rockchip Electronics Co., Ltd
 */

#ifndef __CONFIGS_RK3506_EVB_H
#define __CONFIGS_RK3506_EVB_H

#include <configs/rk3506_common.h>

#ifndef CONFIG_SPL_BUILD

#undef ROCKCHIP_DEVICE_SETTINGS
#define ROCKCHIP_DEVICE_SETTINGS \
		"stdin=serial,usbkbd\0" \
		"stdout=serial,vidconsole\0" \
		"stderr=serial,vidconsole\0"

#define CONFIG_SYS_MMC_ENV_DEV		0

/* Do not override default boot command
#undef CONFIG_BOOTCOMMAND
#define CONFIG_BOOTCOMMAND RKIMG_BOOTCOMMAND */
#endif

/*
 * rearrange addresses to give fdt some more room
 *
 *   (trust):    0K - 392K
 * (ramoops):  524K - 704K
 *     Image:  1M+32k - 17M
 *    zImage:  17M - 24M
 *       fdt:  24M - 25M
 *   ramdisk:  25M - ...
 */
#undef ENV_MEM_LAYOUT_SETTINGS
#define ENV_MEM_LAYOUT_SETTINGS \
        "scriptaddr=0x00b00000\0"       \
        "pxefile_addr_r=0x00c00000\0"   \
        "kernel_addr_r=0x00108000\0"    \
        "kernel_addr_c=0x01100000\0"    \
        "fdt_addr_r=0x01800000\0"       \
        "ramdisk_addr_r=0x01900000\0"

#endif /* __CONFIGS_RK3506_EVB_H */
