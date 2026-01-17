import argparse
import contextlib
import pathlib
import sys
import tempfile
import termios
import tty

from .build import Build
from . import discover
from .resources import Resource
from .sources import Sources


def _read_one_char():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def main():
    with contextlib.ExitStack() as ctx:
        main_with_ctx(ctx)


def main_with_ctx(ctx):
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
    print()
    if src_res.check_and_print(ctx):
        print()
        sys.exit(1)

    try:
        src = Sources(src_res.path)
    except Sources.SyntaxError as e:
        print('Error loading overlay source tree:')
        print(str(e))
        print()
        sys.exit(1)

    cfg = discover.config('-c/--config', args.config, write=not args.dry_run)
    out = discover.output('-o/--output', args.output)
    dt = discover.device_tree('-d/--device-tree', args.device_tree)

    build_dir = ctx.enter_context(
        tempfile.TemporaryDirectory(prefix='lyra-overlays.'))

    build_dir = pathlib.Path(build_dir)
    build = Build(build_dir, src=src, cfg=cfg, out=out, dt=dt)

    resources = []
    resources += build.prepare_resources
    if not args.skip_config:
        resources += build.configure_resources
    resources += build.build_resources
    if not args.skip_check:
        resources += build.check_resources
    if not args.dry_run:
        if not args.skip_config:
            resources += build.install_config_resources
        resources += build.install_build_resources

    if Resource.check_and_print_all(ctx, resources):
        print()
        sys.exit(1)

    build.prepare()
    if not args.skip_config:
        build.configure()

    build.build()
    if not args.skip_check:
        while not build.check():
            print('', file=sys.stderr)

            retry = False
            if not args.skip_config and not args.batch:
                while True:
                    print('Reconfigure [Y/n]? ', file=sys.stderr, end='')
                    sys.stderr.flush()
                    y_or_n = _read_one_char()
                    if y_or_n.upper() not in 'YN\r\n':
                        print('', file=sys.stderr)
                        print('Please enter Y or N.', file=sys.stderr)
                    else:
                        break
                print(y_or_n, file=sys.stderr)
                if y_or_n.upper() in 'Y\r\n':
                    retry = True

            if not retry:
                print('ERROR: resolve these problems and retry.',
                      file=sys.stderr)
                sys.exit(1)

            build.configure()
            build.clean()
            build.build()

    if not args.dry_run:
        build.install_build()
        if not args.skip_config:
            build.install_config()


if __name__ == '__main__':
    main()
