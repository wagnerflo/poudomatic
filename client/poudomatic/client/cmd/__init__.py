from click import group,option,pass_context
from configparser import ConfigParser
from pathlib import Path
from sys import base_prefix

from .. import PoudomaticClient
from .build import build,buildlog
from .depends import depends
from .info import info
from .ports import ports

def configure(ctx, param, filenames):
    filenames = [Path(filenames)] if filenames is not None else [
        item / "poudomatic.ini" for item in [
            Path("~/.config").expanduser(),
            Path("/" if base_prefix == "/usr" else base_prefix) / "etc",
        ]
    ]

    cfg = ConfigParser(interpolation=None)
    for filename in filenames:
        if filename.is_file():
            cfg.read(filename)
            break

    ctx.default_map = {
        "endpoint": []
    }

    for section in cfg.sections():
        first,*rest = section.split(maxsplit=1)
        rest = rest.pop() if rest else None

        if first == "endpoint":
            ctx.default_map["endpoint"].append(rest.strip())

@group()
@option(
    "-c", "--config",
    default      = None,
    callback     = configure,
    is_eager     = True,
    expose_value = False,
    help         = "Read configuration from INI file",
)
@option(
    "-e", "--endpoint",
    multiple = True,
)
@pass_context
def main(ctx, endpoint):
    ctx.meta["client"] = ctx.with_resource(
        PoudomaticClient(endpoint)
    )

# main.add_command(depends)
main.add_command(build)
main.add_command(buildlog)
main.add_command(info)
main.add_command(ports)

__all__ = (
    "main",
)
