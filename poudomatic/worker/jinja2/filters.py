from itertools import count,product
from jinja2.ext import Extension
from pathlib import Path
from shlex import quote as shquote

class FiltersExtension(Extension):
    heredoc_chars = (
        '^!%*+,.:<>?~@0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        'abcdefghijklmnopqrstuvwxyz$"#&()-/=;[]_|${}'
    )

    def __init__(self, environment):
        super().__init__(environment)
        environment.filters.update(
            shquote = self._shquote,
            dirname = self._dirname,
            basename = self._basename,
            makevar = self._makevar,
            heredoc = self._heredoc,
        )

    def _shquote(self, arg):
        return shquote(str(arg))

    def _dirname(self, arg):
        return str(Path(arg).parent)

    def _basename(self, arg):
        return str(Path(arg).name)

    def _makevar(self, arg):
        if (arg := str(arg)):
            arg = arg.replace('\n', '${.newline}').replace('"', '\\"')
            if arg[0] in ' \t' or arg[-1] in ' \t':
                return f'"{arg}"'
        return arg

    def _heredoc(self, arg):
        if not arg.endswith('\n'):
            arg = arg + '\n'
        for i in count(1):
            for word in product(self.heredoc_chars, repeat=i):
                word = ''.join(word)
                if word not in arg:
                    return f"'{word}'\n{arg}{word}"

__all__ = (
    "FiltersExtension",
)
