import contextlib
import datetime
import pathlib
import shutil
import subprocess
import sys
import typing

import libfdt  # type: ignore

from .devicetree import DeviceTree
from .resources import Resource
from .sources import DtsoRule, Sources


__all__ = [
    'Build', 'Step',
    'Prepare', 'Config', 'Compile', 'Check',
    'InstallOverlays', 'InstallConfig',
]


class Build:
    class PromptReconfigure(Exception):
        pass

    def __init__(self, path: pathlib.Path, src: Sources):
        self._path = path
        self._src = src

        self._cfg_updated = False
        self._dtbo_updated = False

    def log(self, typ: str, line: pathlib.Path | str) -> None:
        print(f'  {typ.upper():7s} {line}')

    @property
    def path(self) -> pathlib.Path:
        return self._path

    @property
    def src(self) -> Sources:
        return self._src

    @property
    def local_cfg(self) -> pathlib.Path:
        return self._path / 'lyra-overlays.config'

    @property
    def local_header(self) -> pathlib.Path:
        return self._path / 'config.h'

    @property
    def local_dt(self) -> pathlib.Path:
        return self._path / 'lyra-overlays-applied.dtb'

    @property
    def cfg_updated(self) -> bool:
        return self._cfg_updated

    @cfg_updated.setter
    def cfg_updated(self, v: bool) -> None:
        self._cfg_updated = v

    @property
    def dtbo_updated(self) -> bool:
        return self._dtbo_updated

    @dtbo_updated.setter
    def dtbo_updated(self, v: bool) -> None:
        self._dtbo_updated = v

    def clean(self) -> None:
        for p in self._path.glob('*.dtbo'):
            self.log('rm', p.name)
            p.unlink()

    @contextlib.contextmanager
    def open_with_header(self, path: pathlib.Path, header: str,
                         prefix: str = '') -> typing.Iterator[typing.IO[str]]:
        with open(path, 'w') as dest:
            lines = header.splitlines()

            # trim blank first and last lines
            if lines and lines[0].strip() == '':
                del lines[0]
            if lines and lines[-1].strip() == '':
                del lines[-1]

            # figure out the indentation of the first line
            indent = ''
            if lines:
                indent = lines[0][0:-len(lines[0].lstrip())]

            for line in lines:
                if line.startswith(indent):
                    line = line[len(indent):]

                line = f'{prefix}{line.strip()}'
                print(line, file=dest)

            yield dest

    def install_with_header(self, src_path: pathlib.Path,
                            dest_path: pathlib.Path, header: str,
                            prefix: str = '') -> None:
        with open(src_path) as src:
            with self.open_with_header(
                    dest_path, header, prefix=prefix) as dest:
                print('', file=dest)
                shutil.copyfileobj(src, dest)

    def install_string(self, path: pathlib.Path, contents: str,
                       prefix: str = '') -> None:
        with self.open_with_header(path, contents, prefix=prefix):
            pass


class Step:
    @property
    def resources(self) -> list[Resource]:
        return []

    def run(self, build: Build) -> None:
        raise NotImplementedError


class Prepare(Step):
    def __init__(self, cfg: Resource):
        super().__init__()
        self._cfg = cfg

    @property
    def resources(self) -> list[Resource]:
        return [self._cfg]

    def run(self, build: Build) -> None:
        if not build.cfg_updated:
            if self._cfg.exists():
                build.src.olddefconfig(self._cfg.path, build.local_cfg)
            else:
                with open(build.local_cfg, 'w') as f:
                    # FIXME default
                    f.write('')


class Config(Step):
    def run(self, build: Build) -> None:
        build.src.menuconfig(build.local_cfg)
        build.cfg_updated = True


class Compile(Step):
    def run(self, build: Build) -> None:
        uname_proc = subprocess.run(['uname', '-r'],
                                    check=True, capture_output=True)
        uname = uname_proc.stdout.decode('utf-8').strip()
        cpp_flags = [
            '-nostdinc', '-undef', '-x', 'assembler-with-cpp',
            '-I', '/usr/src/linux-headers-' + uname + '/include/',
            '-I', str(build.src.include),
            '-I', str(build.path),
        ]

        build.src.genconfig(build.local_cfg, build.local_header)

        for rule in build.src.get_active_rules(build.local_cfg):
            if isinstance(rule, DtsoRule):
                self._build_dtso(build, cpp_flags, rule)

        build.dtbo_updated = True

    def _build_dtso(self, build: Build, cpp_flags: list[str],
                    rule: DtsoRule) -> None:
        build.log('dtc', rule.target)
        out_path = build.path / rule.output
        if out_path.exists():
            raise RuntimeError(
                f'duplicate overlay name detected: {rule.output}')

        with open(out_path, 'wb') as out:
            cpp = subprocess.Popen(['cpp', *cpp_flags, rule.target],
                                   stdout=subprocess.PIPE)
            dts = subprocess.Popen(['dtc', '-I', 'dts', '-O', 'dtb'],
                                   stdin=cpp.stdout, stdout=out)
            if cpp.stdout is not None:
                cpp.stdout.close()
            if dts.wait():
                sys.exit(1)


class Check(Step):
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

    def __init__(self, dt: Resource):
        super().__init__()
        self._dt = dt

    @property
    def resources(self) -> list[Resource]:
        return [self._dt]

    def run(self, build: Build) -> None:
        shutil.copyfile(self._dt.path, build.local_dt)

        for rule in build.src.get_active_rules(build.local_cfg):
            if isinstance(rule, DtsoRule):
                build.log('check', rule.output)
                self._overlay_dtbo(build.local_dt, build.path / rule.output)

        check_dt = DeviceTree(build.local_dt)
        if not self._check_pins(check_dt):
            raise Build.PromptReconfigure('some pins used multiple times')

    def _check_pins(self, check_dt: DeviceTree) -> bool:
        pinmap: dict[str, list[tuple[str, str, str]]] = {}
        symbols = {}
        names = {}
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
                    names[node] = {
                        f'pinctrl-{i}': s
                        for i, s in enumerate(props[k].as_stringlist())
                    }
                    continue
                for phandle in props[k].as_list('I'):
                    node_off = dtb.node_offset_by_phandle(phandle)
                    self._check_pinctrl(
                        check_dt, dtb, node_off, pinmap, node, k)

        success = True
        for pin, users in pinmap.items():
            # only one user is always fine
            if len(users) == 1:
                continue

            # more than one user is fine as long as
            # * all of them are the same node
            # * all of them are distinct properties
            first_user, first_prop, _ = users[0]
            if all(u[0] == first_user and u[1] != first_prop
                   for u in users[1:]):
                continue

            success = False

            rmio = None
            name = pin
            if pin in self._RMIO:
                rmio = self._RMIO.index(pin)
                name = f'{rmio} ({pin})'

            print('', file=sys.stderr)
            print(f'ERROR: pin {name} is used more than once:',
                  file=sys.stderr)
            for (user, prop, pinctrl) in users:
                pinctrl_name = names.get(user, {}).get(prop)
                pinctrl_name = f' ({pinctrl_name!r})'
                if user in symbols:
                    user = '&' + symbols[user]
                print(f'  {user:20s} {prop}{pinctrl_name} {pinctrl}',
                      file=sys.stderr)

        return success

    def _check_pinctrl(
            self,
            check_dt: DeviceTree,
            dtb: libfdt.FdtRo,
            node_off: int,
            pinmap: dict[str, list[tuple[str, str, str]]],
            user: str,
            user_prop: str,
    ) -> None:

        for dtb, node, props in check_dt.walk_node(dtb, node_off):
            if 'rockchip,pins' not in props:
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
                # function = pin[2]
                # config = pin[3]

                pinmap.setdefault(name, []).append((user, user_prop, node))

    def _overlay_dtbo(self, dtb: pathlib.Path, overlay: pathlib.Path) -> None:
        try:
            subprocess.run(['fdtoverlay', '-i', dtb, '-o', dtb, overlay],
                           check=True)
        except subprocess.CalledProcessError:
            sys.exit(1)


class InstallOverlays(Step):
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

    def __init__(self, out: Resource):
        super().__init__()
        self._out = out

    @property
    def resources(self) -> list[Resource]:
        return [self._out]

    def run(self, build: Build) -> None:
        if not build.dtbo_updated:
            return

        self._out.path.mkdir(parents=True, exist_ok=True)

        for p in self._out.path.glob('*.dtbo'):
            build.log('rm', p)
            p.unlink()

        for rule in build.src.get_active_rules(build.local_cfg):
            if isinstance(rule, DtsoRule):
                in_path = build.path / rule.output
                out_path = self._out.path / rule.output
                build.log('install', out_path)
                shutil.copyfile(in_path, out_path)

        backup_cfg = self._out.path / 'lyra-overlays.config.bak'
        build.log('install', backup_cfg)
        build.install_with_header(build.local_cfg, backup_cfg,
                                  self._CONFIG_BACKUP_HEADER, prefix='# ')

        output_readme = self._out.path / 'README'
        build.log('install', output_readme)
        build.install_string(output_readme, self._OUTPUT_README)


class InstallConfig(Step):
    _CONFIG_INSTALL_HEADER = f"""
    THIS FILE IS GENERATED. ({datetime.datetime.now().isoformat()})

    If you wish to edit this file, use the lyra-overlays tool.
    """

    def __init__(self, cfg: Resource):
        super().__init__()
        self._cfg = cfg

    @property
    def resources(self) -> list[Resource]:
        return [self._cfg]

    def run(self, build: Build) -> None:
        if not build.cfg_updated:
            return

        build.log('install', self._cfg.path)
        build.install_with_header(build.local_cfg, self._cfg.path,
                                  self._CONFIG_INSTALL_HEADER, prefix='# ')
