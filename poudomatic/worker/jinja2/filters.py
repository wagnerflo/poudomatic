from jinja2.ext import Extension
from pathlib import Path
from shlex import quote as shquote

class FiltersExtension(Extension):
    def __init__(self, environment):
        super().__init__(environment)
        environment.filters.update(
            shquote = self._shquote,
            dirname = self._dirname,
            makevar = self._makevar,
        )

    def _shquote(self, arg):
        return shquote(str(arg))

    def _dirname(self, arg):
        return str(Path(arg).parent)

    def _makevar(self, arg):
        if (arg := str(arg)):
            arg = arg.replace('\n', '${.newline}').replace('"', '\\"')
            if arg[0] in ' \t' or arg[-1] in ' \t':
                return f'"{arg}"'
        return arg

__all__ = (
    "FiltersExtension",
)
