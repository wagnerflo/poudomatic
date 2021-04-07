from time import time
from types import SimpleNamespace
from ..common import unblocked

class Port:
    def __init__(self, category, portname, template, collection):
        self.category = category
        self.portname = portname
        self.template = template
        self.collection = collection
        self.poudomatic_dependencies = None
        self.origin = f"{self.category}/{self.portname}"

    @unblocked
    def generate(self, env, base, fetchdir):
        portsdir = base / self.category / self.portname
        portsdir.mkdir()

        metadata = SimpleNamespace(
            install = [],
            plist = [],
            build_depends = [],
            run_depends = [],
        )
        context = dict(
            portname = self.portname,
            category = self.category,
            fetchdir = fetchdir.relative_to(base),
            collection = self.collection,
            metadata = metadata,
        )
        tmpl = env.runtime.get_template(self.template)

        with (portsdir / 'Makefile').open('w') as fp:
            tmpl.stream(context).dump(fp)

        # with (portsdir / 'Makefile').open() as fp:
        #     for line in fp.readlines():
        #         print(line, end='')

        with (portsdir / 'pkg-plist').open('w') as fp:
            for item in metadata.plist:
                fp.write(f"{item}\n")

        with (portsdir / 'pkg-descr').open('w') as fp:
            pass

        with (portsdir / 'distinfo').open('w') as fp:
            fp.write(f"TIMESTAMP = {int(time())}\n")

        self.poudomatic_dependencies = (
            metadata.build_depends +
            metadata.run_depends
        )
