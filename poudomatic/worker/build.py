from pathlib import Path
from types import SimpleNamespace
from ..common import mkdir,to_thread
from .target import Target

class Port:
    def __init__(self, category, name, template, target):
        self.category = category
        self.name = name
        self.template = template
        self.target = target

    @property
    def fullname(self):
        return f"{self.category}/{self.name}"

    @to_thread
    def generate(self, env, base, fetchdir):
        portsdir = base / self.category / self.name
        portsdir.mkdir()

        metadata = SimpleNamespace(
            install = [],
            plist = [],
        )
        context = dict(
            portname = self.name,
            category = self.category,
            fetchdir = fetchdir.name,
            metadata = metadata,
        )
        tmpl = env.runtime.get_template(self.template)

        with (portsdir / 'Makefile').open('w') as fp:
            tmpl.stream(context).dump(fp)

        with (portsdir / 'pkg-plist').open('w') as fp:
            for item in metadata.plist:
                fp.write(f"{item}\n")

        with (portsdir / 'pkg-descr').open('w') as fp:
            pass

        with (portsdir / 'distinfo').open('w') as fp:
            fp.write(f"TIMESTAMP = {int(self.target.timestamp)}\n")

class Build:
    def __init__(self, env, jail_version, ports_branch, target_uri):
        self.env = env
        self.jail_version = jail_version
        self.ports_branch = ports_branch
        self.target_uri = target_uri

    def __await__(self):
        return self.run().__await__()

    async def run(self):
        env = self.env
        jail = await env.get_jail(self.jail_version)
        ports = await env.get_ports(self.ports_branch)

        targets = {}
        allports = {}
        to_build = set()

        async with ports.install() as (portsfs, portsname):
            portsdir = Path(portsfs.mountpoint)
            workdir = portsdir / "POUDOMATIC"
            await mkdir(workdir)

            try:
                target = await Target.fetch(self.target_uri, workdir)
                targets[target.key] = target

                for template in await target.templates():
                    category,_,portname = template.stem.partition('_')
                    port = Port(category, portname, template, target)

                    if port.fullname in allports:
                        continue

                    allports[port.fullname] = port
                    to_build.add(port)

                    await port.generate(env, portsdir, target.path)

                await (
                    await (
                        env.poudriere(
                            "bulk", "-j", jail.name, "-p", portsname,
                            *(port.fullname for port in to_build)
                        )
                        >> env.runtime.log
                    )
                )

            finally:
                for target in targets.values():
                    await target.cleanup()
