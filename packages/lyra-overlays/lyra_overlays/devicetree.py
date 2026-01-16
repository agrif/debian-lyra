import libfdt  # type: ignore


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
