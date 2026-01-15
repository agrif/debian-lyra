import argparse
import contextlib
import importlib.resources
import os
import pathlib
import sys
import tempfile
import termios
import tty

from .build import Build
from .devicetree import DeviceTree
from .sources import Sources


def _read_one_char():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


class Configuration:
    def __init__(self, path):
        self._path = path

    @classmethod
    def discover(cls):
        return pathlib.Path('/etc/lyra-overlays.config')

    @property
    def path(self):
        return self._path

    def exists(self):
        return self._path.is_file()

    def is_writeable(self):
        # best effort, this is a UI feature
        if self.exists():
            return os.access(self._path, os.W_OK)
        return os.access(self._path.parent, os.W_OK)

    def generate_default(self):
        # FIXME
        return ''


class Output:
    def __init__(self, path):
        self._path = path

    @classmethod
    def discover(cls):
        return pathlib.Path('/boot/overlays/lyra-overlays/')

    @property
    def path(self):
        return self._path

    def exists(self):
        return self._path.is_dir()

    def is_writeable(self):
        # best effort, this is a UI feature
        try:
            os.makedirs(self._path, exist_ok=True)
            return os.access(self._path, os.W_OK)
        except Exception:
            return False


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

    src_path = args.source if args.source else Sources.discover()
    if not src_path:
        resources = importlib.resources.files('lyra_overlays.overlays')
        src_path = ctx.enter_context(importlib.resources.as_file(resources))
    src = Sources(src_path)

    cfg_path = args.config if args.config else Configuration.discover()
    cfg = Configuration(cfg_path)

    out_path = args.output if args.output else Output.discover()
    out = Output(out_path)

    dt_path = args.device_tree if args.device_tree else DeviceTree.discover()
    if not args.skip_check:
        if not dt_path:
            print('ERROR: could not find DT to check against',
                  file=sys.stderr)
            sys.exit(1)
        dt = DeviceTree(dt_path)
        if dt_path and not dt.exists():
            print(f'ERROR: device tree does not exist: {dt_path}',
                  file=sys.stderr)
            sys.exit(1)
    else:
        dt = None

    build_dir = ctx.enter_context(
        tempfile.TemporaryDirectory(prefix='lyra-overlays.'))

    build_dir = pathlib.Path(build_dir)
    build = Build(build_dir, src=src, cfg=cfg, out=out, dt=dt)

    if not args.dry_run:
        perms = []
        if not args.skip_config:
            perms += build.install_config_check_permissions()
        perms += build.install_build_check_permissions()

        if perms:
            print('ERROR: I need permission to write to the following:',
                  file=sys.stderr)
            print('', file=sys.stderr)
            for fname in perms:
                print('  ', fname, file=sys.stderr)
            print('', file=sys.stderr)
            print('You may want to run as root, or use options to',
                  file=sys.stderr)
            print('override those locations.', file=sys.stderr)
            sys.exit(1)

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
