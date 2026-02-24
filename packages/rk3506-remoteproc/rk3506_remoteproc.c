// SPDX-License-Identifier: GPL-2.0+
/*
 * RK3506 Remote Processor Control Driver
 *
 * Author: Aaron Griffith <aargri@gmail.com>
 */

#include <linux/arm-smccc.h>
#include <linux/clk.h>
#include <linux/mfd/syscon.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/regmap.h>
#include <linux/remoteproc.h>
#include <linux/reset.h>

#include "hw_bitfield.h"

/* SMC call constants */
#define SIP_MCU_CFG					0x82000028
#define ROCKCHIP_SIP_CONFIG_BUSMCU_0_ID			0x00
#define ROCKCHIP_SIP_CONFIG_MCU_CODE_START_ADDR		0x01

/* PMU registers and fields */
#define PMU_INT_MASK_CON	0x000c
#define   GLB_INT_MASK_MCU	BIT(1)
#define   MCU_RST_DIS_CFG	BIT(2)

struct rk3506_rproc {
	struct regmap *pmu;

	void __iomem *fw_mem;
	struct resource *fw_res;

	struct reset_control *resets;
	struct clk_bulk_data *clks;
	int num_clks;
};

static void rk3506_rproc_set_enabled(struct rk3506_rproc *ddata, bool en)
{
	if (en)
		regmap_write(ddata->pmu, PMU_INT_MASK_CON,
			     FIELD_PREP_WM16(MCU_RST_DIS_CFG, 1) |
			     FIELD_PREP_WM16(GLB_INT_MASK_MCU, 0));
	else
		regmap_write(ddata->pmu, PMU_INT_MASK_CON,
			     FIELD_PREP_WM16(MCU_RST_DIS_CFG, 0) |
			     FIELD_PREP_WM16(GLB_INT_MASK_MCU, 1));
}

static int rk3506_rproc_start(struct rproc *rproc)
{
	struct rk3506_rproc *ddata = rproc->priv;
	struct device *dev = &rproc->dev;
	int ret;
	struct arm_smccc_res res;

	/* Stop the processor if it's running to force a reset. */
	rk3506_rproc_set_enabled(ddata, false);

	ret = clk_bulk_prepare_enable(ddata->num_clks, ddata->clks);
	if (ret) {
		dev_err(dev, "failed to enable clocks\n");
		return ret;
	}

	ret = reset_control_deassert(ddata->resets);
	if (ret) {
		dev_err(dev, "failed to deassert resets\n");
		return ret;
	}

	arm_smccc_smc(SIP_MCU_CFG, ROCKCHIP_SIP_CONFIG_BUSMCU_0_ID,
		      ROCKCHIP_SIP_CONFIG_MCU_CODE_START_ADDR,
		      ddata->fw_res->start, 0, 0, 0, 0, &res);
	if (res.a0) {
		dev_err(dev, "failed to set start address\n");
		return -EIO;
	}

	rk3506_rproc_set_enabled(ddata, true);

	dev_info(&rproc->dev, "start\n");
	return 0;
}

static int rk3506_rproc_stop(struct rproc *rproc)
{
	struct rk3506_rproc *ddata = rproc->priv;

	rk3506_rproc_set_enabled(ddata, false);
	reset_control_assert(ddata->resets);
	clk_bulk_disable_unprepare(ddata->num_clks, ddata->clks);

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

	/* Grab handles to register blocks we need. */
	ddata->pmu = syscon_regmap_lookup_by_phandle(np, "rockchip,pmu");
	if (IS_ERR(ddata->pmu))
		return dev_err_probe(dev, PTR_ERR(ddata->pmu),
				     "failed to get PMU");

	/* Map memory where firmware will be loaded. */
	ddata->fw_mem = devm_platform_get_and_ioremap_resource(pdev, 0,
							       &ddata->fw_res);
	if (IS_ERR(ddata->fw_mem))
		return dev_err_probe(dev, PTR_ERR(ddata->fw_mem),
				     "failed to map firmware memory\n");

	/* Grab all clocks and resets. */
	ddata->num_clks = devm_clk_bulk_get_all(dev, &ddata->clks);
	if (ddata->num_clks < 0)
		return ddata->num_clks;

	ddata->resets = devm_reset_control_array_get_exclusive(dev);
	if (IS_ERR(ddata->resets))
		return PTR_ERR(ddata->resets);

	/* We're ready to go. */
	ret = devm_rproc_add(dev, rproc);
	if (ret)
		return ret;

	platform_set_drvdata(pdev, rproc);
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
