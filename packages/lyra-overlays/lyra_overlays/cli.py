import argparse
import contextlib
import dataclasses
import datetime
import importlib.resources
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import termios
import tty

import kconfiglib
import libfdt


class LBuildError(Exception):
    pass


@contextlib.contextmanager
def _wrap_kconfig(kconfig, reset=True):
    """Wrap calls into kconfiglib to promote warnings to errors."""
    if reset:
        kconfig.warnings = []
    yield kconfig
    if kconfig.warnings:
        raise RuntimeError('\n'.join(kconfig.warnings))


def _read_one_char():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


@dataclasses.dataclass
class Rule:
    target: pathlib.Path
    condition: str | None

    def is_active(self, kconfig):
        if self.condition:
            with _wrap_kconfig(kconfig):
                return kconfig.eval_string(self.condition) > 0
        return True

    def evaluate(self, kconfig):
        if self.is_active(kconfig):
            yield self


@dataclasses.dataclass
class DtsoRule(Rule):
    @property
    def output(self):
        return self.target.with_suffix('.dtbo').name


@dataclasses.dataclass
class SubdirRule(Rule):
    subrules: list[Rule]

    def evaluate(self, kconfig):
        yield from super().evaluate(kconfig)
        if self.is_active(kconfig):
            for rule in self.subrules:
                yield from rule.evaluate(kconfig)


class Sources:
    def __init__(self, path):
        self._path = path
        self._lbuild_path = path / 'Lbuild'
        self._kconfig_path = path / 'Kconfig'

        os.environ['srctree'] = str(path)
        self._kconfig = kconfiglib.Kconfig(self._kconfig_path,
                                           warn_to_stderr=False)
        with _wrap_kconfig(self._kconfig, reset=False):
            pass

        self._lbuild = self._read_lbuild(path)

    @classmethod
    def discover(self):
        here = pathlib.Path(__file__)
        local = here.parent / 'overlays'

        paths = [local]
        for path in paths:
            kconfig = path / 'Kconfig'
            lbuild = path / 'Lbuild'
            if path.is_dir() and kconfig.is_file() and lbuild.is_file():
                return path

        return None

    @property
    def path(self):
        return self._path

    @property
    def include(self):
        return self._path / 'include'

    def _read_lbuild(self, path):
        lbuild_path = path / 'Lbuild'
        lbuild = []
        with open(lbuild_path) as f:
            for line_no, line in enumerate(f):
                if '#' in line:
                    line, _ = line.split('#', 1)
                line = line.strip()
                if not line:
                    continue

                target, *expr = line.split()
                try:
                    rule = self._parse_rule(path / target, ' '.join(expr))
                except LBuildError as e:
                    raise
                except Exception as e:
                    raise LBuildError(
                        f'error at {lbuild_path}:{line_no + 1}') from e

                lbuild.append(rule)

        return lbuild

    def _parse_rule(self, target, condition):
        if not condition:
            condition = None

        if condition:
            with _wrap_kconfig(self._kconfig):
                self._kconfig.eval_string(condition)

        if target.is_dir():
            subrules = self._read_lbuild(target)
            return SubdirRule(target, condition, subrules)
        elif target.is_file():
            if target.suffix == '.dtso':
                return DtsoRule(target, condition)
            else:
                raise ValueError(f'no rules for file: {target}')
        else:
            raise ValueError(f'file does not exist: {target}')

    def load_config(self, config_path):
        with _wrap_kconfig(self._kconfig):
            self._kconfig.load_config(config_path)
        return self._kconfig

    def get_active_rules(self, config_path):
        self.load_config(config_path)
        for rule in self._lbuild:
            yield from rule.evaluate(self._kconfig)

    def _call_kconfig(self, name, config_path, *args):
        env = os.environ.copy()
        env['KCONFIG_CONFIG'] = config_path
        subprocess.run([sys.executable, '-m', name, *args], env=env, check=True)

    def genconfig(self, config_path, output_path):
        self.load_config(config_path).write_autoconf(output_path)

    def menuconfig(self, config_path):
        self._call_kconfig('menuconfig', config_path)
        self.load_config(config_path)

    def olddefconfig(self, config_path, output_path):
        self.load_config(config_path).write_config(output_path)

    def savedefconfig(self, config_path, output_path):
        self.load_config(config_path).write_min_config(output_path)


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


class DeviceTree:
    def __init__(self, path):
        self._path = path

    @classmethod
    def discover(cls):
        # FIXME
        return None

    @property
    def path(self):
        return self._path

    def exists(self):
        return self._path.is_file()

    def walk(self):
        with open(self._path, 'rb') as dtb:
            dtb = libfdt.FdtRo(dtb.read())

        yield from self.walk_node(dtb, 0)

    def _iter_properties(self, dtb, node_off):
        try:
            off = dtb.first_property_offset(node_off)
        except libfdt.FdtException:
            off = None

        while off is not None:
            yield dtb.get_property_by_offset(off)

            try:
                off = dtb.next_property_offset(off)
            except libfdt.FdtException:
                off = None

    def _iter_subnodes(self, dtb, node_off):
        try:
            off = dtb.first_subnode(node_off)
        except libfdt.FdtException:
            off = None

        while off is not None:
            yield off

            try:
                off = dtb.next_subnode(off)
            except libfdt.FdtException:
                off = None

    def walk_node(self, dtb, node_off, parent=[]):
        name = dtb.get_name(node_off)
        path = parent[:] + [name]

        props = {}
        for prop in self._iter_properties(dtb, node_off):
            props[prop.name] = prop

        yield (dtb, '/'.join(path), props)

        for subnode_off in self._iter_subnodes(dtb, node_off):
            yield from self.walk_node(dtb, subnode_off, parent=path)


class Builder:
    _CONFIG_INSTALL_HEADER = f"""
    THIS FILE IS GENERATED. ({datetime.datetime.now().isoformat()})

    If you wish to edit this file, use the lyra-overlays tool.
    """

    _CONFIG_BACKUP_HEADER = f"""
    THIS FILE IS GENERATED. ({datetime.datetime.now().isoformat()})

    This file is a backup of the file used to generate the overlays in
    this directory. Editing it will not do anything. Instead, use the
    lyra-overlays tool.
    """

    _OUTPUT_README = f"""
    THIS DIRECTORY IS GENERATED ({datetime.datetime.now().isoformat()})

    The overlays in this directory are generated by lyra-overlays. If
    you modify these files directly, those changes may be lost the
    next time lyra-overlays is run.
    """

    _RMIO = [
        # 0
        'GPIO0_A0', 'GPIO0_A1', 'GPIO0_A2', 'GPIO0_A3',
        'GPIO0_A4', 'GPIO0_A5', 'GPIO0_A6', 'GPIO0_A7',
        # 8
        'GPIO0_B0', 'GPIO0_B1', 'GPIO0_B2', 'GPIO0_B3',
        'GPIO0_B4', 'GPIO0_B5', 'GPIO0_B6', 'GPIO0_B7',
        # 16
        'GPIO0_C0', 'GPIO0_C1', 'GPIO0_C2', 'GPIO0_C3',
        'GPIO0_C4', 'GPIO0_C5', 'GPIO0_C6', 'GPIO0_C7',
        # 24
        'GPIO1_B1', 'GPIO1_B2', 'GPIO1_B3', 'GPIO1_C2',
        'GPIO1_C3', 'GPIO1_D1', 'GPIO1_D2', 'GPIO1_D3',
    ]

    def __init__(self, path, src, cfg, out, dt):
        self._path = path
        self._src = src
        self._cfg = cfg
        self._out = out
        self._dt = dt

        uname = subprocess.run(['uname', '-r'], check=True, capture_output=True)
        uname = uname.stdout.decode('utf-8').strip()
        self._cpp_flags = [
            '-nostdinc', '-undef', '-x', 'assembler-with-cpp',
            '-I', '/usr/src/linux-headers-' + uname + '/include/',
            '-I', self._src.include,
            '-I', self._path,
        ]

        self._local_cfg = path / 'lyra-overlays.config'
        self._local_h = path / 'config.h'
        self._local_check = path / 'lyra-overlays-check.dtb'
        self._backup_cfg = self._out.path / 'lyra-overlays.config.bak'
        self._output_readme = self._out.path / 'README'

        if self._cfg.exists():
            self._src.olddefconfig(self._cfg.path, self._local_cfg)
        else:
            with open(self._local_cfg, 'w') as f:
                f.write(self._cfg.generate_default())

        self._cfg_updated = False
        self._build_updated = False

    def _log(self, typ, line):
        print(f'  {typ.upper():7s} {line}')

    def configure(self):
        self._src.menuconfig(self._local_cfg)
        self._cfg_updated = True

    def clean(self):
        for p in self._path.glob('*.dtbo'):
            self._log('rm', p.name)
            p.unlink()

    def build(self):
        self._src.genconfig(self._local_cfg, self._local_h)

        for rule in self._src.get_active_rules(self._local_cfg):
            if isinstance(rule, DtsoRule):
                self._build_dtso(rule)

        self._build_updated = True

    def _build_dtso(self, rule):
        self._log('dtc', rule.target)
        out_path = self._path / rule.output
        if out_path.exists():
            raise RuntimeError(
                f'duplicate overlay name detected: {rule.output}')

        with open(out_path, 'wb') as out:
            cpp = subprocess.Popen(['cpp', *self._cpp_flags, rule.target],
                                   stdout=subprocess.PIPE)
            dts = subprocess.Popen(['dtc', '-I', 'dts', '-O', 'dtb'],
                                   stdin=cpp.stdout, stdout=out)
            cpp.stdout.close()
            if dts.wait():
                sys.exit(1)

    def check(self):
        shutil.copyfile(self._dt.path, self._local_check)

        for rule in self._src.get_active_rules(self._local_cfg):
            if isinstance(rule, DtsoRule):
                self._log('check', rule.output)
                self._overlay_dtbo(self._local_check, self._path / rule.output)

        check_dt = DeviceTree(self._local_check)
        return self._check_pins(check_dt)

    def _check_pins(self, check_dt):
        pinmap = {}
        symbols = {}
        for dtb, node, props in check_dt.walk():
            if node == '/__symbols__':
                symbols = {v.as_str(): k for k, v in props.items()}
                continue
            if 'status' in props and props['status'] != b'okay\0':
                continue
            for k in props:
                if not k.startswith('pinctrl-'):
                    continue
                if k == 'pinctrl-names':
                    continue
                for phandle in props[k].as_list('I'):
                    node_off = dtb.node_offset_by_phandle(phandle)
                    self._check_pinctrl(check_dt, dtb, node_off, pinmap, node)

        success = True
        for pin, users in pinmap.items():
            if len(set(user for user, _ in users)) == 1:
                continue

            success = False

            rmio = None
            name = pin
            if pin in self._RMIO:
                rmio = self._RMIO.index(pin)
                name = f'{rmio} ({pin})'

            print('', file=sys.stderr)
            print(f'ERROR: pin {name} is used more than once:', file=sys.stderr)
            for (user, pinctrl) in users:
                if user in symbols:
                    user = '&' + symbols[user]
                print(f'  {user:20s} (pinctrl: {pinctrl})', file=sys.stderr)

        return success

    def _check_pinctrl(self, check_dt, dtb, node_off, pinmap, user):
        for dtb, node, props in check_dt.walk_node(dtb, node_off):
            if not 'rockchip,pins' in props:
                raise RuntimeError(f'pinctrl with no pins: {node}')
            pins = props['rockchip,pins'].as_list('I')
            if not len(pins) % 4 == 0:
                raise RuntimeError(f'pinctrl with bad format: {node}')
            for i in range(0, len(pins), 4):
                pin = pins[i:i + 4]

                bank = pin[0]
                letter = chr(ord('A') + pin[1] // 8)
                number = pin[1] % 8
                name = f'GPIO{bank}_{letter}{number}'
                function = pin[2]
                config = pin[3]

                pinmap.setdefault(name, []).append((user, node))

    def _overlay_dtbo(self, dtb, overlay):
        try:
            subprocess.run(['fdtoverlay', '-i', dtb, '-o', dtb, overlay],
                           check=True)
        except subprocess.CalledProcessError:
            sys.exit(1)

    def _install_with_header(self, header, src_path, dest_path):
        with open(src_path) as src:
            with open(dest_path, 'w') as dest:
                for line in header.splitlines():
                    line = f'# {line.strip()}'
                    print(line, file=dest)
                print('', file=dest)
                shutil.copyfileobj(src, dest)

    def install_build_check_permissions(self):
        if not self._out.is_writeable():
            return [self._out.path]
        return []

    def install_build(self):
        if not self._build_updated:
            return

        for p in self._out.path.glob('*.dtbo'):
            self._log('rm', p)
            p.unlink()

        for rule in self._src.get_active_rules(self._local_cfg):
            if isinstance(rule, DtsoRule):
                in_path = self._path / rule.output
                out_path = self._out.path / rule.output
                self._log('install', out_path)
                shutil.copyfile(in_path, out_path)

        self._log('install', self._backup_cfg)
        self._install_with_header(
            self._CONFIG_BACKUP_HEADER, self._local_cfg, self._backup_cfg)

        self._log('install', self._output_readme)
        with open(self._output_readme, 'w') as out:
            for line in self._OUTPUT_README.splitlines():
                line = line.strip()
                print(line, file=out)

    def install_config_check_permissions(self):
        if not self._cfg.is_writeable():
            return [self._cfg.path]
        return []

    def install_config(self):
        if not self._cfg_updated:
            return

        self._log('install', self._cfg.path)
        self._install_with_header(
            self._CONFIG_INSTALL_HEADER, self._local_cfg, self._cfg.path)


def main():
    with contextlib.ExitStack() as ctx:
        main_with_ctx(ctx)


def main_with_ctx(ctx):
    parser = argparse.ArgumentParser()

    parser.add_argument('-n', '--dry-run', action='store_true',
        help='configure and build only, do not install or update config')
    parser.add_argument('--skip-config', action='store_true',
        help='skip the configuration menu, use existing config unmodified')
    parser.add_argument('--skip-check', action='store_true',
        help='skip the overlay checks')
    parser.add_argument('-b', '--batch', action='store_true',
        help='do not ask for input')

    parser.add_argument('-s', '--source', type=pathlib.Path,
        help='override source location of overlays')
    parser.add_argument('-c', '--config', type=pathlib.Path,
        help='override configuration path to use')
    parser.add_argument('-o', '--output', type=pathlib.Path,
        help='override output path for overlays')
    parser.add_argument('-d', '--device-tree', type=pathlib.Path,
        help='override device tree to test against')

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
            print(f'ERROR: could not find DT to check against',
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
    build = Builder(build_dir, src=src, cfg=cfg, out=out, dt=dt)

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
