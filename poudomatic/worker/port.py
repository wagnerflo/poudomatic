from itertools import chain
from time import time
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

        metadata = env.runtime.render_port(
            self.template, portsdir / 'Makefile',
            portname = self.portname,
            category = self.category,
            fetchdir = fetchdir.relative_to(base),
            collection = self.collection,
        )

        with (portsdir / 'pkg-plist').open('w') as fp:
            for item in metadata.plist:
                fp.write(f"{item}\n")

        with (portsdir / 'pkg-descr').open('w') as fp:
            descr = metadata.description or metadata.comment
            if descr:
                fp.write(f"{descr.rstrip()}\n\n")
            fp.write(f"WWW: {self.collection.uri}\n")

        with (portsdir / 'distinfo').open('w') as fp:
            fp.write(f"TIMESTAMP = {int(time())}\n")

        self.poudomatic_dependencies = list(
            chain.from_iterable(metadata.depends.values())
        )
