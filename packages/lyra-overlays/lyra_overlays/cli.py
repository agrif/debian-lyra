import argparse
import contextlib
import pathlib
import sys
import tempfile

from . import build
from . import discover
from . import interact
from .resources import Resource
from .sources import Sources


def main() -> None:
    with contextlib.ExitStack() as ctx:
        main_with_ctx(ctx)


def main_with_ctx(ctx: contextlib.ExitStack) -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '-n', '--dry-run', action='store_true',
        help='configure and build only, do not install or update config',
    )
    parser.add_argument(
        '--skip-config', action='store_true',
        help='skip the configuration menu, use existing config unmodified',
    )
    parser.add_argument(
        '--skip-check', action='store_true',
        help='skip the overlay checks',
    )
    parser.add_argument(
        '-b', '--batch', action='store_true',
        help='do not ask for input',
    )

    parser.add_argument(
        '-s', '--source', type=pathlib.Path,
        help='override source location of overlays',
    )
    parser.add_argument(
        '-c', '--config', type=pathlib.Path,
        help='override configuration path to use',
    )
    parser.add_argument(
        '-o', '--output', type=pathlib.Path,
        help='override output path for overlays',
    )
    parser.add_argument(
        '-d', '--device-tree', type=pathlib.Path,
        help='override device tree to test against',
    )

    args = parser.parse_args()

    # batch implies skipping config
    if args.batch:
        args.skip_config = True

    src_res = discover.sources('-s/--sources', args.source)
    cfg = discover.config('-c/--config', args.config,
                          write=not (args.dry_run or args.skip_config))
    out = discover.output('-o/--output', args.output)
    dt = discover.device_tree('-d/--device-tree', args.device_tree)

    steps: list[build.Step] = []

    steps += [build.Prepare(cfg=cfg)]
    if not args.skip_config:
        steps += [build.Config()]
    steps += [build.Compile()]
    if not args.skip_check:
        steps += [build.Check(dt=dt)]
    if not args.dry_run:
        steps += [build.InstallOverlays(out=out)]
        if not args.skip_config:
            steps += [build.InstallConfig(cfg=cfg)]

    resources = [src_res]
    for step in steps:
        resources += step.resources

    if not Resource.check_and_print_all(ctx, resources):
        print()
        sys.exit(1)

    try:
        src = Sources(src_res.path)
    except Sources.SyntaxError as e:
        print('Error loading overlay source tree:')
        print(str(e))
        print()
        sys.exit(1)

    build_dir = ctx.enter_context(
        tempfile.TemporaryDirectory(prefix='lyra-overlays.'))
    b = build.Build(pathlib.Path(build_dir), src)

    running = True
    while running:
        running = False
        b.clean()

        try:
            for step in steps:
                step.run(b)
        except build.Build.PromptReconfigure as e:
            print('')
            print(f'ERROR: {e}')

            if not args.skip_config and not args.batch:
                running = interact.prompt_yes_no('Reconfigure?')

            if not running:
                sys.exit(1)


if __name__ == '__main__':
    main()
