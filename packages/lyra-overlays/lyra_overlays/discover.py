from collections.abc import Callable
import pathlib

from . import resources as res


__all__ = ['config', 'device_tree', 'output', 'sources']


def _generic(
        resource_name: str,
        option_name: str,
        override_type: Callable[[pathlib.Path], res.Resource],
        override: str | None,
        base: list[res.Resource],
        optional: bool = False,
) -> res.Resource:

    if override is None:
        banner = [f'Could not find {resource_name}:']
        resources = [
            res.Failure(f'no {option_name} option provided'),
        ] + base
    else:
        banner = [f'Could not use {resource_name} from {option_name}:']
        resources = [
            override_type(pathlib.Path(override)),
        ]

    return res.Search(resources, banner, optional=optional)


def config(option_name: str, override: str | None,
           write: bool = False) -> res.Resource:

    cls: type[res.ReadFile] | type[res.WriteFile] = res.ReadFile
    if write:
        cls = res.WriteFile

    return _generic('configuration', option_name, cls, override, [
        cls('/etc/lyra-overlays.config'),
    ], optional=not write)


def device_tree(option_name: str, override: str | None) -> res.Resource:
    return _generic('base device tree', option_name, res.ReadFile, override, [
        # following logic in u-boot-update
        res.UBootMenu(
            res.ReadFile,
            '${U_BOOT_FDT}',
        ),
        res.UBootMenu(
            res.ReadFile,
            '${_BOOT_PATH}${U_BOOT_FDT_DIR}${_VERSION}/${U_BOOT_FDT}',
        ),
        res.UBootMenu(
            res.ReadFile,
            '${_BOOT_PATH}/${U_BOOT_FDT:-dtb-${_VERSION}}',
        ),
    ])


def output(option_name: str, override: str | None) -> res.Resource:
    return _generic(
        'overlay output directory', option_name, res.WriteDir, override, [
            # following logic in u-boot-update
            res.UBootMenu(
                # do *not* makedirs here, only use this if the versioned
                # base path exists
                lambda path: res.WriteDir(path, makedirs=False),
                '${_BOOT_PATH}/${U_BOOT_FDT_OVERLAYS_DIR}${_VERSION}'
                + '/lyra-overlays/',
            ),
            res.UBootMenu(
                lambda path: res.WriteDir(path, makedirs=True),
                '${_BOOT_PATH}/${U_BOOT_FDT_OVERLAYS_DIR}/lyra-overlays/',
            ),
        ],
    )


def output_uboot(option_name: str, override: str | None) -> res.Resource:
    return _generic(
        'u-boot-menu output directory', option_name, res.WriteDir, override, [
            res.UBootMenu(
                lambda path: res.WriteDir(path, makedirs=True),
                '/etc/u-boot-menu/conf.d/',
            ),
        ],
    )


def sources(option_name: str, override: str | None) -> res.Resource:
    here = pathlib.Path(__file__)
    packaged = here.parent / 'overlays'

    return _generic('overlay sources', option_name, res.ReadDir, override, [
        res.ReadDir(packaged),
        res.ReadModuleDir('lyra_overlays.overlays'),
    ])
