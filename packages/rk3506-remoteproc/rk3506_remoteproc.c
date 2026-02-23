// SPDX-License-Identifier: GPL-2.0+
/*
 * RK3506 Remote Processor Control Driver
 *
 * Author: Aaron Griffith <aargri@gmail.com>
 */

#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>

static int rk3506_rproc_probe(struct platform_device *pdev)
{
	dev_info(&pdev->dev, "probe");
	return -ENODEV;
}

static void rk3506_rproc_remove(struct platform_device *pdev)
{
	dev_info(&pdev->dev, "remove");
}

static const struct of_device_id rk3506_rproc_match[] = {
	{ .compatible = "rockchip,rk3506-rproc" },
	{ .compatible = "rockchip,rk3506-mcu" }, // FIXME remove
	{},
};
MODULE_DEVICE_TABLE(of, rk3506_rproc_match);

static struct platform_driver rk3506_rproc_driver = {
	.probe = rk3506_rproc_probe,
	.remove_new = rk3506_rproc_remove,
	.driver = {
		.name = "rk3506-rproc",
		.of_match_table = of_match_ptr(rk3506_rproc_match),
	},
};
module_platform_driver(rk3506_rproc_driver);

MODULE_DESCRIPTION("RK3506 Remote Processor Control Driver");
MODULE_AUTHOR("Aaron Griffith <aargri@gmail.com>");
MODULE_LICENSE("GPL");
