import contextlib
import importlib.resources
import os
import pathlib


__all__ = [
    'Resource', 'Failure', 'Search', 'ReadModuleDir', 'ReadFile', 'WriteFile',
    'ReadDir', 'WriteDir',
]


class Resource:
    @property
    def path(self) -> pathlib.Path:
        raise NotImplementedError

    def exists(self) -> bool:
        return False

    def check(self, ctx: contextlib.ExitStack) -> list[str]:
        return []

    def check_and_print(self, ctx: contextlib.ExitStack) -> bool:
        msgs = self.check(ctx)
        if msgs:
            for m in msgs:
                print(m)
            return True
        return False

    @classmethod
    def check_and_print_all(cls, ctx: contextlib.ExitStack,
                            resources: list['Resource']) -> bool:
        failed = False
        needs_line = False
        for r in set(resources):
            msgs = r.check(ctx)
            if msgs:
                if needs_line:
                    print()
                    needs_line = False
                for m in msgs:
                    print(m)
                failed = True
                needs_line = True
        return failed


class Failure(Resource):
    def __init__(self, *messages: str):
        self._messages = list(messages)

    def check(self, ctx: contextlib.ExitStack) -> list[str]:
        return self._messages


class Search(Resource):
    class StopSearch(Exception):
        def __init__(self, messages: list[str]):
            super().__init__()
            self._messages = messages

        @property
        def messages(self) -> list[str]:
            return self._messages

    def __init__(self, resources: list[Resource], banner: list[str],
                 optional: bool = False):
        self._resources = resources
        self._banner = list(banner)
        self._optional = optional
        self._found: Resource | None = None

    @property
    def path(self) -> pathlib.Path:
        if self._found is None:
            raise RuntimeError('must call check() first')
        return self._found.path

    @property
    def optional(self) -> bool:
        return self._optional

    def exists(self) -> bool:
        if self._found is None:
            return False
        return self._found.exists()

    def check(self, ctx: contextlib.ExitStack) -> list[str]:
        messages = self._banner[:]
        stop = False
        for r in self._resources:
            try:
                ms = r.check(ctx)
            except self.StopSearch as e:
                ms = e.messages
                stop = True
            if not ms:
                self._found = r
                return []
            messages += [f' * {m}' for m in ms]
            if stop:
                break
        if self._optional:
            return []
        return messages


class ReadModuleDir(Resource):
    def __init__(self, module: str):
        self._module = module
        self._path: pathlib.Path | None = None

    @property
    def path(self) -> pathlib.Path:
        if self._path is None:
            raise RuntimeError('must call check() first')
        return self._path

    def exists(self) -> bool:
        if self._path is None:
            return False
        return self._path.exists()

    def check(self, ctx: contextlib.ExitStack) -> list[str]:
        try:
            resources = importlib.resources.files(self._module)
        except Exception:
            return [f'module `{self._module}` not found']

        try:
            path = ctx.enter_context(importlib.resources.as_file(resources))
        except Exception:
            return [f'module `{self._module}` cannot be extracted']

        if not path.is_dir():
            return [f'module `{self._module}` is not a directory']

        self._path = path
        return []


class _PathResource(Resource):
    def __init__(self, path: pathlib.Path | str):
        self._path = pathlib.Path(path)

    @property
    def path(self) -> pathlib.Path:
        return self._path

    def exists(self) -> bool:
        return self._path.exists()


class ReadFile(_PathResource):
    def check(self, ctx: contextlib.ExitStack) -> list[str]:
        if not self._path.exists():
            return [f'`{self._path}` does not exist']
        if not self._path.is_file():
            raise Search.StopSearch([f'`{self._path}` is not a file'])
        if not os.access(self._path, os.R_OK):
            raise Search.StopSearch([f'`{self._path}` is not readable'])
        return []


class WriteFile(_PathResource):
    def __init__(self, path, makedirs=False):
        super().__init__(path)
        self._makedirs = makedirs

    def check(self, ctx: contextlib.ExitStack) -> list[str]:
        if self._path.exists():
            if not self._path.is_file():
                return [f'`{self._path}` is not a file']
            if not os.access(self._path, os.R_OK):
                raise Search.StopSearch([f'`{self._path}` is not readable'])
            if not os.access(self._path, os.W_OK):
                raise Search.StopSearch([f'`{self._path}` is not writeable'])
            return []

        for parent in self._path.parents:
            if not parent.exists():
                if not self._makedirs:
                    return [f'`{self._path}` is not createable']
                continue
            if not parent.is_dir():
                return [f'`{self._path}` is not createable']
            if not os.access(parent, os.W_OK):
                return [f'`{self._path}` is not writeable']
            return []

        # no parent path exists? weird
        return [f'`{self._path}` is not createable']


class ReadDir(_PathResource):
    def check(self, ctx: contextlib.ExitStack) -> list[str]:
        if not self._path.exists():
            return [f'`{self._path}` does not exist']
        if not self._path.is_dir():
            raise Search.StopSearch([f'`{self._path}` is not a directory'])
        if not os.access(self._path, os.R_OK):
            raise Search.StopSearch([f'`{self._path}` is not readable'])
        return []


class WriteDir(_PathResource):
    def __init__(self, path, makedirs=False):
        super().__init__(path)
        self._makedirs = makedirs

    def check(self, ctx: contextlib.ExitStack) -> list[str]:
        if self._path.exists():
            if not self._path.is_dir():
                return [f'`{self._path}` is not a directory']
            if not os.access(self._path, os.R_OK):
                raise Search.StopSearch([f'`{self._path}` is not readable'])
            if not os.access(self._path, os.W_OK):
                raise Search.StopSearch([f'`{self._path}` is not writeable'])
            return []

        for parent in self._path.parents:
            if not parent.exists():
                if not self._makedirs:
                    return [f'`{self._path}` is not createable']
                continue
            if not parent.is_dir():
                return [f'`{self._path}` is not createable']
            if not os.access(parent, os.W_OK):
                return [f'`{self._path}` is not writeable']
            return []

        # no parent path exists? weird
        return [f'`{self._path}` is not createable']
