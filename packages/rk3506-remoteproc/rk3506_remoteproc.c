// SPDX-License-Identifier: GPL-2.0+
/*
 * RK3506 Remote Processor Control Driver
 *
 * Author: Aaron Griffith <aargri@gmail.com>
 */

#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/remoteproc.h>

struct rk3506_rproc {
	void __iomem *fw_mem;
	struct resource *fw_res;
};

static int rk3506_rproc_start(struct rproc *rproc)
{
	dev_info(&rproc->dev, "start\n");
	return 0;
}

static int rk3506_rproc_stop(struct rproc *rproc)
{
	dev_info(&rproc->dev, "stop\n");
	return 0;
}

static void rk3506_rproc_kick(struct rproc *rproc, int vqid)
{
	dev_info(&rproc->dev, "kick %i\n", vqid);
}

static void *rk3506_rproc_da_to_va(struct rproc *rproc, u64 da, size_t len,
				   bool *is_iomem)
{
	struct rk3506_rproc *ddata = rproc->priv;
	struct resource *fw_res = ddata->fw_res;

	dev_info(&rproc->dev, "da_to_va da=%llx len=%zu\n", da, len);

	if (da + len <= fw_res->end - fw_res->start + 1) {
		if (is_iomem)
			*is_iomem = true;
		return ddata->fw_mem + da;
	}

	return NULL;
}

static const struct rproc_ops rk3506_rproc_ops = {
	.start		= rk3506_rproc_start,
	.stop		= rk3506_rproc_stop,
	.kick		= rk3506_rproc_kick,
	.da_to_va	= rk3506_rproc_da_to_va,
};

static int rk3506_rproc_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct device_node *np = dev->of_node;
	const char *fw_name;
	struct rproc *rproc;
	struct rk3506_rproc *ddata;
	int ret;

	/* This is rproc_of_parse_firmware in remoteproc_internal.h */
	ret = of_property_read_string(np, "firmware-name", &fw_name);
	if (ret < 0 && ret != -EINVAL)
		return ret;

	rproc = devm_rproc_alloc(dev, np->name, &rk3506_rproc_ops, fw_name,
				 sizeof(*ddata));
	if (!rproc)
		return -ENOMEM;

	ddata = rproc->priv;

	ddata->fw_mem = devm_platform_get_and_ioremap_resource(pdev, 0,
							       &ddata->fw_res);
	if (IS_ERR(ddata->fw_mem))
		return dev_err_probe(dev, PTR_ERR(ddata->fw_mem),
				     "failed to map firmware memory\n");

	ret = devm_rproc_add(dev, rproc);
	if (ret)
		return ret;

	dev_info(dev, "probe fw_name: %s fw: %zx - %zx\n",
		 fw_name, ddata->fw_res->start, ddata->fw_res->end);
	return 0;
}

static void rk3506_rproc_remove(struct platform_device *pdev)
{
	dev_info(&pdev->dev, "remove\n");
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
