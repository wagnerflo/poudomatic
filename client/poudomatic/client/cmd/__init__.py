from click import group
from .build import build
from .depends import depends

@group()
def main():
    pass

main.add_command(depends)
main.add_command(build)

__all__ = (
    "main",
)
