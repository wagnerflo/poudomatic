from collections import deque
from pathlib import Path
from tempfile import mkdtemp
from ..common import cleanup,unblocked

from .collection import Collection
from .port import Port

class Build:
    def __init__(self, env, jail_version, ports_branch, collection_uri):
        self.env = env
        self.jail_version = jail_version
        self.ports_branch = ports_branch
        self.collection_uri = collection_uri

    def __await__(self):
        return self.run().__await__()

    @cleanup
    async def run(self):
        env = self.env
        jail = await env.get_jail(self.jail_version)
        portstree = await cleanup.push(env.activate_ports(self.ports_branch))

        collections = {}
        generated = set()
        to_build = set()
        to_resolve = deque()

        async def fetch_collection(uri):
            return Collection.new(
                uri,
                Path(await unblocked(mkdtemp, dir=portstree.workdir))
            )

        col = await cleanup.push(await fetch_collection(self.collection_uri))
        collections[col.uri] = col

        # initial seed of ports
        async for port in col:
            to_build.add(port)
            to_resolve.append(port)

        # resolve dependencies
        while to_resolve:
            if (port := to_resolve.pop()).origin in generated:
                continue

            # generate the port
            await port.generate(env, portstree.path, col.path)
            generated.add(port.origin)

            # walk all dependencies
            for dep in port.poudomatic_dependencies:

                # not managed by poudomatic or already known?
                if dep.is_external or dep.origin in generated:
                    continue

                # get the specified collection if necessary
                if dep.uri not in collections:
                    col = collections[dep.uri] = await cleanup.push(
                        await fetch_collection(dep.uri)
                    )

                to_resolve.append(
                    await col.get_port(dep.category, dep.portname)
                )

        if to_build:
            await (
                await (
                    env.poudriere(
                        "bulk", "-j", jail.name, "-p", portstree.name,
                        *(port.origin for port in to_build)
                    )
                    >> env.runtime.log
                )
            )
