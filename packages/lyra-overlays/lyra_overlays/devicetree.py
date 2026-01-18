from __future__ import annotations

import dataclasses
import pathlib
import typing

import libfdt  # type: ignore


class DeviceTree:
    """A device tree."""

    def __init__(self, data: bytes):
        """Parse the device tree inside `data`."""
        self._fdt = libfdt.FdtRo(data)

    @classmethod
    def open(cls, path: pathlib.Path | str) -> typing.Self:
        """Open the file at `path` and parse a device tree."""
        with open(path, 'rb') as f:
            return cls(f.read())

    @property
    def data(self) -> bytearray:
        """The device tree contents as a bytearray."""
        return self._fdt.as_bytearray()

    @property
    def root(self) -> Node:
        """The root node of the device tree."""
        return Node(self, 0)

    def all_nodes(self) -> typing.Iterator[Node]:
        """Return an iterator over all nodes in the device tree."""
        off = 0
        depth = 0

        while True:
            try:
                yield Node(self, off)
                off, depth = self._fdt.next_node(off, depth)
            except libfdt.FdtException:
                return

    @property
    def magic(self) -> int:
        """Return the magic word from the header."""
        return self._fdt.magic()

    @property
    def total_size(self) -> int:
        """Return the total size of the device tree."""
        return self._fdt.totalsize()

    @property
    def version(self) -> int:
        """Return the version of the device tree."""
        return self._fdt.version()

    @property
    def last_compatible_version(self) -> int:
        """Return the last compatible version of the device tree."""
        return self._fdt.last_comp_version()

    @property
    def boot_cpuid(self) -> int:
        """Return the physical boot CPU ID."""
        return self._fdt.boot_cpuid_phys()

    def reserved_memory(self) -> typing.Iterator[ReservedMemory]:
        """Return an iterator over reserved memory regions."""
        for i in range(self._fdt.num_mem_rsv()):
            yield ReservedMemory(*self._fdt.get_mem_rsv(i))

    def get_node(self, path: str) -> Node:
        """Return the node at the given full path.

        Raises KeyError if no such node exists.
        """
        try:
            off = self._fdt.path_offset(path)
        except libfdt.FdtException:
            raise KeyError(f'no node at path {path!r}')
        return Node(self, off)

    def get_path_by_alias(self, alias: str) -> str:
        """Look up an alias and return a full node path.

        Raises KeyError if no such alias exists.
        """
        path = self._fdt.get_alias(alias)
        if path is None:
            raise KeyError(f'no alias named {alias!r}')
        return path

    def get_aliases_by_path(self, path: str) -> list[str]:
        """Return the aliases that resolve to the given path."""
        ret = []
        try:
            aliases = self.root.get_subnode('aliases')
            for alias, prop in aliases.properties.items():
                try:
                    if prop.as_str() == path:
                        ret.append(alias)
                except ValueError:
                    pass
        except KeyError:
            pass

        return ret

    def get_path_by_symbol(self, symbol: str) -> str:
        """Look up a symbol and return a full node path.

        Raises KeyError if no such symbol exists."""
        try:
            symbols = self.root.get_subnode('__symbols__')
            prop = symbols.properties.get(symbol)
            try:
                if prop is not None:
                    return prop.as_str()
            except ValueError:
                pass
        except KeyError:
            pass

        raise KeyError(f'no symbol named {symbol!r}')

    def get_symbols_by_path(self, path: str) -> list[str]:
        """Return the symbols that resolve to the given path."""
        ret = []
        try:
            symbols = self.root.get_subnode('__symbols__')
            for symbol, prop in symbols.properties.items():
                try:
                    if prop.as_str() == path:
                        ret.append(symbol)
                except ValueError:
                    pass
        except KeyError:
            pass

        return ret

    def get_node_by_alias(self, alias: str) -> Node:
        """Look up an alias and return a node.

        Raises KeyError if no such node exists.
        """
        return self.get_node(self.get_path_by_alias(alias))

    def get_node_by_phandle(self, phandle: int) -> Node:
        """Look up a phandle and return a node.

        Raises KeyError if no such node exists.
        """
        try:
            off = self._fdt.node_offset_by_phandle(phandle)
        except libfdt.FdtException:
            raise KeyError(f'no node with phandle {phandle!r}')
        return Node(self, off)

    def get_node_by_symbol(self, symbol: str) -> Node:
        """Look up a symbol and return a node.

        Raises KeyError if no such node exists.
        """
        return self.get_node(self.get_path_by_symbol(symbol))


@dataclasses.dataclass
class ReservedMemory:
    """A reserved memory region."""
    address: int
    size: int


class Node:
    """A device tree node."""

    def __init__(self, dt: DeviceTree, offset: int):
        """Load a node from `dt` at `offset`."""
        self._dt = dt
        self._offset = offset
        self._properties: dict[str, Property] | None = None

        # sanity check at creation
        self.name

    def __repr__(self) -> str:
        return f'<Node path={self.path!r}>'

    @property
    def dt(self) -> DeviceTree:
        """Return the device tree this node is part of."""
        return self._dt

    def subnodes(self) -> typing.Iterator[Node]:
        """Return an iterator over subnodes of this node."""
        try:
            off = self._dt._fdt.first_subnode(self._offset)
        except libfdt.FdtException:
            off = None

        while off is not None:
            yield Node(self._dt, off)

            try:
                off = self._dt._fdt.next_subnode(off)
            except libfdt.FdtException:
                off = None

    def walk(self) -> typing.Iterator[Node]:
        """Return an iterator over this node and all subnodes, recursively."""
        yield self
        for node in self.subnodes():
            yield from node.walk()

    @property
    def name(self) -> str:
        """The name of this node."""
        return self._dt._fdt.get_name(self._offset)

    def get_subnode(self, name: str) -> Node:
        """Get a subnode of this node by name.

        Raises KeyError if no such node exists.
        """
        try:
            off = self._dt._fdt.subnode_offset(self._offset, name)
        except libfdt.FdtException:
            raise KeyError(f'no subnode named {name!r}')
        return Node(self._dt, off)

    @property
    def properties(self) -> dict[str, Property]:
        """The properties of this node, as a dictionary."""
        if self._properties is not None:
            return self._properties

        self._properties = {}

        try:
            off = self._dt._fdt.first_property_offset(self._offset)
        except libfdt.FdtException:
            off = None

        while off is not None:
            prop = Property(self._dt._fdt.get_property_by_offset(off))
            self._properties[prop.name] = prop

            try:
                off = self._dt._fdt.next_property_offset(off)
            except libfdt.FdtException:
                off = None

        return self._properties

    @property
    def phandle(self) -> int | None:
        """The phandle of this node, or None if it has no phandle."""
        phandle = self._dt._fdt.get_phandle(self._offset)
        if not phandle:
            return None
        return phandle

    @property
    def path(self) -> str:
        """Return the full path to this node."""
        return self._dt._fdt.get_path(self._offset)

    @property
    def aliases(self) -> list[str]:
        """Return all aliases that resolve to this node."""
        return self._dt.get_aliases_by_path(self.path)

    @property
    def symbols(self) -> list[str]:
        """Return all symbols that resolve to this node."""
        return self._dt.get_symbols_by_path(self.path)

    @property
    def parent(self) -> Node | None:
        """Returns the parent of this node, or None if it has no parent."""
        try:
            off = self._dt._fdt.parent_offset(self._offset)
        except libfdt.FdtException:
            return None
        return Node(self._dt, off)


class Property:
    """A property of a device tree node."""

    def __init__(self, prop: libfdt.Property):
        """Wrap a libfdt property."""
        self._prop = prop

    def __repr__(self) -> str:
        return repr(self._prop)

    def __eq__(self, other: typing.Any) -> bool:
        return self.as_bytearray() == other

    @property
    def name(self) -> str:
        """The name of this property."""
        return self._prop.name

    def as_bytearray(self) -> bytearray:
        """Return the property as a raw bytearray."""
        return self._prop

    def as_format(self, fmt: str) -> typing.Any:
        """Return the property value in the given struct format."""
        return self._prop.as_cell(fmt)

    def as_list(self, fmt: str) -> list[typing.Any]:
        """Return the property as a list of values in the given
        struct format.
        """
        return self._prop.as_list(fmt)

    def as_uint32(self) -> int:
        return self._prop.as_uint32()

    def as_int32(self) -> int:
        return self._prop.as_int32()

    def as_uint64(self) -> int:
        return self._prop.as_uint64()

    def as_int64(self) -> int:
        return self._prop.as_int64()

    def as_uint32_list(self) -> list[int]:
        return self._prop.as_uint32_list()

    def as_int32_list(self) -> list[int]:
        return self._prop.as_int32_list()

    def as_uint64_list(self) -> list[int]:
        return self._prop.as_uint64_list()

    def as_int64_list(self) -> list[int]:
        return self._prop.as_int64_list()

    def as_str(self) -> str:
        return self._prop.as_str()

    def as_str_list(self) -> list[str]:
        return self._prop.as_stringlist()


if __name__ == '__main__':
    import json
    import sys

    _, dt_path = sys.argv
    dt = DeviceTree.open(dt_path)

    print('/dts-v1/;')
    print(f'// magic:\t\t0x{dt.magic:x}')
    print(f'// totalsize:\t\t0x{dt.total_size:x} ({dt.total_size})')
    print(f'// version:\t\t{dt.version}')
    print(f'// last_comp_version:\t{dt.last_compatible_version}')
    print(f'// boot_cpuid_phys:\t0x{dt.boot_cpuid:x}')
    print()

    def walk(node: Node, indent: str = '') -> None:
        old_indent = indent

        print(f'{old_indent}{node.name if node.name else "/"} {{')
        indent += '    '

        for k, prop in node.properties.items():
            if prop.as_bytearray():
                # try as string list
                try:
                    vals = prop.as_str_list()
                    # don't print as strings if it contains empty string
                    if '' in vals:
                        raise ValueError()
                    # don't print as strings if it contains non-printable chars
                    for v in vals:
                        for c in v:
                            if ord(c) < 0x20 or ord(c) > 0x7e:
                                raise ValueError()
                    val = ', '.join(json.dumps(s) for s in prop.as_str_list())
                except Exception:
                    # try as uint32 list
                    try:
                        val = ' '.join(f'0x{v:08x}'
                                       for v in prop.as_uint32_list())
                        val = f'<{val}>'
                    except Exception:
                        # fall back to raw bytes
                        val = ' '.join(f'{v:02x}' for v in prop.as_bytearray())
                        val = f'[{val}]'
                print(f'{indent}{k} = {val};')
            else:
                print(f'{indent}{k};')

        for subnode in node.subnodes():
            walk(subnode, indent=indent)

        print(f'{old_indent}}};')

    walk(dt.root)
