from contextlib import contextmanager
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
        self.generated_files = []

    @contextmanager
    def mark_generated(self, path):
        yield path
        self.generated_files.append(path)

    @unblocked
    def generate(self, env, base, fetchdir):
        portsdir = base / self.category / self.portname
        portsdir.mkdir()

        with self.mark_generated(portsdir / "Makefile") as target:
            metadata = env.runtime.render_port(
                self.template, target,
                portname = self.portname,
                category = self.category,
                fetchdir = fetchdir.relative_to(base),
                collection = self.collection,
            )

        for script,targets in metadata.scripts.items():
            if not any(targets.values()):
                continue

            with self.mark_generated(portsdir / script) as target:
                env.runtime.render_template(
                    "scripts/pkg_script.sh", target,
                    targets=targets,
                )

        self.poudomatic_dependencies = list(
            chain.from_iterable(metadata.depends.values())
        )
