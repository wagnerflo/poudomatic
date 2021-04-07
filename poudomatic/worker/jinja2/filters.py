from jinja2.ext import Extension
from pathlib import Path
from shlex import quote as shquote

class FiltersExtension(Extension):
    def __init__(self, environment):
        super().__init__(environment)
        environment.filters["shquote"] = self._shquote
        environment.filters["dirname"] = self._dirname

    def _shquote(self, arg):
        return shquote(str(arg))

    def _dirname(self, arg):
        return str(Path(arg).parent)

__all__ = (
    "FiltersExtension",
)
