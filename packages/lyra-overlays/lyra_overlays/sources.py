import contextlib
import dataclasses
import os
import pathlib
import subprocess
import sys
import typing

from kconfiglib import Kconfig, KconfigError  # type: ignore


__all__ = ['Rule', 'DtsoRule', 'SubdirRule', 'Sources']


class KconfigWarning(Exception):
    pass


@contextlib.contextmanager
def _wrap_kconfig(
        kconfig: Kconfig,
        reset: bool = True,
) -> typing.Iterator[Kconfig]:

    """Wrap calls into kconfiglib to promote warnings to errors."""
    if reset:
        kconfig.warnings = []
    yield kconfig
    if kconfig.warnings:
        raise KconfigWarning('\n'.join(kconfig.warnings))


@dataclasses.dataclass
class Rule:
    target: pathlib.Path
    condition: str | None

    def is_active(self, kconfig: Kconfig) -> bool:
        if self.condition:
            with _wrap_kconfig(kconfig):
                return kconfig.eval_string(self.condition) > 0
        return True

    def evaluate(self, kconfig: Kconfig) -> typing.Iterator['Rule']:
        if self.is_active(kconfig):
            yield self


@dataclasses.dataclass
class DtsoRule(Rule):
    @property
    def output(self) -> str:
        return self.target.with_suffix('.dtbo').name


@dataclasses.dataclass
class SubdirRule(Rule):
    subrules: list[Rule]

    def evaluate(self, kconfig: Kconfig) -> typing.Iterator[Rule]:
        yield from super().evaluate(kconfig)
        if self.is_active(kconfig):
            for rule in self.subrules:
                yield from rule.evaluate(kconfig)


class Sources:
    class SyntaxError(Exception):
        pass

    class _SimpleSyntaxError(Exception):
        pass

    def __init__(self, path: pathlib.Path):
        self._path = path
        self._lbuild_path = path / 'Lbuild'
        self._kconfig_path = path / 'Kconfig'

        # unfortunately kconfiglib is a bit of a mess
        try:
            os.environ['srctree'] = str(path)
            self._kconfig = Kconfig(self._kconfig_path.name,
                                    warn_to_stderr=False)
            with _wrap_kconfig(self._kconfig, reset=False):
                pass
        except (KconfigError, KconfigWarning) as e:
            raise self.SyntaxError(str(e))

        self._lbuild = self._read_lbuild(path)

    @property
    def path(self) -> pathlib.Path:
        return self._path

    @property
    def include(self) -> pathlib.Path:
        return self._path / 'include'

    def _read_lbuild(self, path: pathlib.Path) -> list[Rule]:
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
                except self.SyntaxError:
                    raise
                except self._SimpleSyntaxError as e:
                    relpath = lbuild_path.relative_to(self._path)
                    raise self.SyntaxError(
                        f'{relpath}:{line_no + 1}: {str(e)}') from e

                lbuild.append(rule)

        return lbuild

    def _parse_rule(self, target: pathlib.Path, condition: str | None) -> Rule:
        if not condition:
            condition = None

        reltarget = target.relative_to(self._path)

        if condition:
            try:
                with _wrap_kconfig(self._kconfig):
                    self._kconfig.eval_string(condition)
            except KconfigWarning as e:
                raise self._SimpleSyntaxError(str(e)) from e

        if target.is_dir():
            subrules = self._read_lbuild(target)
            return SubdirRule(target, condition, subrules)
        elif target.is_file():
            if target.suffix == '.dtso':
                return DtsoRule(target, condition)
            else:
                raise self._SimpleSyntaxError(
                    f'no rules for file: {reltarget}')
        else:
            raise self._SimpleSyntaxError(
                f'file does not exist: {reltarget}')

    def _load_config(self, config_path: pathlib.Path) -> Kconfig:
        with _wrap_kconfig(self._kconfig):
            self._kconfig.load_config(config_path)
        return self._kconfig

    def get_active_rules(self,
                         config_path: pathlib.Path) -> typing.Iterator[Rule]:
        self._load_config(config_path)
        for rule in self._lbuild:
            yield from rule.evaluate(self._kconfig)

    def _call_kconfig(self, name: str, config_path: pathlib.Path,
                      *args: str) -> None:
        env = os.environ.copy()
        env['KCONFIG_CONFIG'] = str(config_path)
        subprocess.run([sys.executable, '-m', name, *args],
                       env=env, check=True)

    def genconfig(self, config_path: pathlib.Path,
                  output_path: pathlib.Path) -> None:
        self._load_config(config_path).write_autoconf(output_path)

    def menuconfig(self, config_path: pathlib.Path) -> None:
        self._call_kconfig('menuconfig', config_path)
        self._load_config(config_path)

    def olddefconfig(self, config_path: pathlib.Path,
                     output_path: pathlib.Path) -> None:
        self._load_config(config_path).write_config(output_path)

    def savedefconfig(self, config_path: pathlib.Path,
                      output_path: pathlib.Path) -> None:
        self._load_config(config_path).write_min_config(output_path)
