from pathlib import Path
from ..common import mkdir
from .target import Target

class Build:
    def __init__(self, env, jail_version, ports_branch, target_uri):
        self.env = env
        self.jail_version = jail_version
        self.ports_branch = ports_branch
        self.target_uri = target_uri

    def __await__(self):
        return self.run().__await__()

    async def mkport(self, workdir, target):
        pass

    async def run(self):
        env = self.env
        jail = await env.get_jail(self.jail_version)
        ports = await env.get_ports(self.ports_branch)
        targets = {}

        async with ports.install() as (portsfs, portsname):
            portsdir = Path(portsfs.mountpoint)
            workdir = portsdir / "POUDOMATIC"
            await mkdir(workdir)

            try:
                target = await Target.fetch(self.target_uri, workdir)
                targets[target.key] = target

                async with jail.start(portsname) as jexec:
                    await (
                        await (
                            jexec("/bin/ls", "-l", "/usr/ports/POUDOMATIC")
                            >> env.runtime.log
                        )
                    )
                    import asyncio
                    await asyncio.sleep(600)

            finally:
                for target in targets.values():
                    await target.cleanup()
