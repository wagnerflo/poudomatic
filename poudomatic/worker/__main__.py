import asyncio

from argparse import ArgumentParser
from sys import exit

from .environment import Environment
from .runtime import ConsoleRuntime

async def create_jail(env, args):
    await env.create_jail(args.version)

async def create_ports(env, args):
    await env.create_ports(args.branch)

async def run_build(env, args):
    await env.build(args.jail, args.ports, args.target)

async def run(args):
    rt = await ConsoleRuntime.new()
    env = await Environment.new(args.dataset, rt)
    return await args.func(env, args)

def main():
    root = ArgumentParser()
    root.add_argument(
        "dataset", metavar="DATASET", help=(
            "ZFS dataset to use as Poudomatic's enviroment root."
        )
    )
    root_sub = root.add_subparsers(
        required=True, metavar="COMMAND"
    )

    # JAIL handling
    jail = root_sub.add_parser(
        "jail", help="Manage build jails."
    )
    jail_sub = jail.add_subparsers(
        required=True, metavar="COMMAND"
    )

    jail_create = jail_sub.add_parser(
        "create", help="Create a new jail."
    )
    jail_create.add_argument(
        "version", metavar="VERSION", help=(

        )
    )
    jail_create.set_defaults(func=create_jail)

    # PORTS handling
    ports = root_sub.add_parser(
        "ports", help="Manage ports trees."
    )
    ports_sub = ports.add_subparsers(
        required=True, metavar="COMMAND"
    )

    ports_create = ports_sub.add_parser(
        "create", help="Create a new ports tree."
    )
    ports_create.add_argument(
        "branch", metavar="BRANCH", help=(

        )
    )
    ports_create.set_defaults(func=create_ports)

    # BUILD handling
    build = root_sub.add_parser(
        "build", help="Run one-shot builds."
    )
    build.add_argument(
        "jail", help=(

        ),
    )
    build.add_argument(
        "ports", help=(

        ),
    )
    build.add_argument(
        "target",
        help=(
            "URI of a target to build. Supported protocols are file:PATH "
            "(plain directory) and git+[GITURL] (Git repository cloneable "
            "from GITURL)."
        ),
    )
    build.set_defaults(func=run_build)

    try:
        return asyncio.run(run(root.parse_args()))
    except KeyboardInterrupt:
        pass

exit(main() or 0)
