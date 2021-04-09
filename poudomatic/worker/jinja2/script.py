from itertools import groupby
from jinja2 import nodes
from jinja2.ext import Extension
from jinja2.exceptions import TemplateSyntaxError
from jinja2.lexer import describe_token
from jinja2_rendervars import RenderVar

from ...common import head

class ScriptExtension(Extension):
    tags = frozenset(["script"])
    tpe_map = {
        "pre_install":    ("pkg-install",   "PRE-INSTALL"),
        "post_install":   ("pkg-install",   "POST-INSTALL"),
        "deinstall":      ("pkg-deinstall", "DEINSTALL"),
        "pre_deinstall":  ("pkg-deinstall", "DEINSTALL"),
        "post_deinstall": ("pkg-deinstall", "POST-DEINSTALL"),
    }

    @RenderVar("scripts", tpe_map=tpe_map)
    def scripts(tpe_map):
        return {
            l1: { l2: [] for _,l2 in l2 }
            for l1,l2 in groupby(sorted(tpe_map.values()), head)
        }

    def parse(self, parser):
        stream = parser.stream
        lineno = next(stream).lineno
        token = next(stream)

        if (entry := self.tpe_map.get(token.value)) is None:
            raise TemplateSyntaxError(
                f"unexpected token {describe_token(name)!r}",
                name.lineno, stream.name, stream.filename,
            )

        return nodes.CallBlock(
            self.call_method(
                "_append",
                [nodes.Const(part, lineno=lineno) for part in entry],
                lineno=lineno
            ),
            [], [],
            parser.parse_statements(
                ("name:endscript",), drop_needle=True
            ),
            lineno=lineno
        )

    def _append(self, l1, l2, caller):
        self.scripts[l1][l2].append(caller())
        return ""

__all__ = (
    "ScriptExtension",
)
