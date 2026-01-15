import contextlib
import dataclasses
import os
import pathlib
import subprocess
import sys

import kconfiglib


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
                except LBuildError:
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
        subprocess.run([sys.executable, '-m', name, *args],
                       env=env, check=True)

    def genconfig(self, config_path, output_path):
        self.load_config(config_path).write_autoconf(output_path)

    def menuconfig(self, config_path):
        self._call_kconfig('menuconfig', config_path)
        self.load_config(config_path)

    def olddefconfig(self, config_path, output_path):
        self.load_config(config_path).write_config(output_path)

    def savedefconfig(self, config_path, output_path):
        self.load_config(config_path).write_min_config(output_path)
