from asyncio import create_subprocess_exec
from collections import deque
from enum import Enum
from pathlib import Path
from tempfile import mkdtemp

from ..common import cleanup,unblocked
from .collection import Collection
from .port import Port

class BuildMode(Enum):
    BUILD   = 1
    INSPECT = 2
    TEST    = 3

@cleanup
async def run_build(env, jail_version, ports_branch, collection_uri, mode, mode_opts=None):
    jail = await env.get_jail(jail_version)
    portstree = await cleanup.push(env.activate_ports(ports_branch))

    collections = {}
    generated = {}
    to_build = set()
    to_resolve = deque()

    async def fetch_collection(uri):
        return Collection.new(
            uri,
            Path(await unblocked(mkdtemp, dir=portstree.workdir))
        )

    col = await cleanup.push(await fetch_collection(collection_uri))
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
        generated[port.origin] = port

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

    # user only wants to inspect generated files
    if mode is BuildMode.INSPECT:
        if (port := generated.get(mode_opts.origin)) is None:
            env.runtime.log("No files generated for '{mode_opts.origin}'.")

        else:
            await (
                await create_subprocess_exec(
                    "/usr/bin/less", "-R",
                    *( path.relative_to(portstree.path)
                       for path in port.generated_files ),
                cwd = portstree.path,
            )
        ).wait()

    # only run poudriere if we found ports in the collection
    elif not to_build:
        env.runtime.log("No ports to build/test.")

    elif mode is BuildMode.BUILD:
        await (
            await (
                env.poudriere(
                    "bulk", "-j", jail.name, "-p", portstree.name,
                    *(port.origin for port in to_build)
                )
                >> env.runtime.log
            )
        )

    elif mode is BuildMode.TEST:
        await (
            await (
                env.poudriere(
                    "testport", "-j", jail.name, "-p", portstree.name,
                    "-o", mode_opts.origin
                )
                >> env.runtime.log
            )
        )
