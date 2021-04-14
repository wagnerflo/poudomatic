import asyncio

from argparse import ArgumentParser
from sys import exit
from types import SimpleNamespace

from .build import BuildMode
from .environment import Environment
from .runtime import ConsoleRuntime

async def create_jail(env, args):
    await env.create_jail(args.version)

async def create_ports(env, args):
    await env.create_ports(args.branch)

async def run_build(env, args):
    await env.build(
        args.jail, args.ports, args.target,
        BuildMode.BUILD, None
    )

async def run_inspect(env, args):
    await env.build(
        args.jail, args.ports, args.target,
        BuildMode.INSPECT, SimpleNamespace(origin=args.origin)
    )

async def run_testport(env, args):
    await env.build(
        args.jail, args.ports, args.target,
        BuildMode.TEST, SimpleNamespace(origin=args.origin)
    )

async def run(args):
    rt = await ConsoleRuntime.new()
    env = await Environment.new(args.dataset, rt)
    return await args.func(env, args)

def need_jail(parser, name, metavar=None):
    parser.add_argument(
        name,
        metavar=name.upper() if metavar is None else metavar,
        help=(
            "FreeBSD system version of the jail to work on/with."
        ),
    )

def need_ports(parser, name, metavar=None):
    parser.add_argument(
        name,
        metavar=name.upper() if metavar is None else metavar,
        help=(
            "Ports branch version to work on/with."
        ),
    )

def need_target(parser, name, metavar=None):
    parser.add_argument(
        name,
        metavar=name.upper() if metavar is None else metavar,
        help=(
            "URI of a target to build. Supported protocols are file:PATH "
            "(plain directory) and git+[GITURL] (Git repository cloneable "
            "from GITURL)."
        ),
    )

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
    need_jail(jail_create, "version")
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
    need_ports(ports_create, "branch")
    ports_create.set_defaults(func=create_ports)

    # BUILD handling
    build = root_sub.add_parser(
        "build", help="Run one-shot builds."
    )
    need_jail(build, "jail")
    need_ports(build, "ports")
    need_target(build, "target")
    build.set_defaults(func=run_build)

    # INSPECT handling
    inspect = root_sub.add_parser(
        "inspect", help="Inspect generated ports definitions."
    )
    inspect.add_argument(
        "-o", "--origin", metavar="ORIGIN", help=(
            "Only show files generated for port ORIGIN."
        )
    )
    need_jail(inspect, "jail")
    need_ports(inspect, "ports")
    need_target(inspect, "target")
    inspect.set_defaults(func=run_inspect)

    # TESTPORT handling
    testport = root_sub.add_parser(
        "testport", help="Run a test build of a single port."
    )
    need_jail(testport, "jail")
    need_ports(testport, "ports")
    need_target(testport, "target")
    testport.add_argument(
        "origin", metavar="ORIGIN", help=(
            "Origin of the port to test."
        )
    )
    testport.set_defaults(func=run_testport)

    try:
        return asyncio.run(run(root.parse_args()))
    except KeyboardInterrupt:
        pass

exit(main() or 0)
