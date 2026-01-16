import pathlib

from . import resources as res


def _generic(
        resource_name: str,
        option_name: str,
        override: str | None,
        base: list[res.Resource],
) -> res.Resource:

    if override is None:
        resources = [
            res.Failure(f'no {option_name} option provided'),
        ] + base
    else:
        resources = [
            res.ReadDir(override),
            res.Failure(f'{option_name} provided, no other locations searched')
        ]

    return res.Search(resources, f'Could not find {resource_name}:')


def sources(option_name: str, override: str | None) -> res.Resource:
    here = pathlib.Path(__file__)
    packaged = here.parent / 'overlays'

    return _generic('overlay sources', option_name, override, [
        res.ReadDir(packaged),
        res.ReadModuleDir('lyra_overlays.overlays'),
    ])
