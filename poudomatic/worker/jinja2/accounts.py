from jinja2 import nodes
from jinja2.ext import Extension
from jinja2_rendervars import RenderVar

from .base import (
    parse_keywords,
    parse_name_as_const,
)

class AccountsExtension(Extension):
    tags = frozenset(["user", "group"])
    user = RenderVar("users", dict)
    group = RenderVar("groups", dict)

    def parse(self, parser):
        token = next(parser.stream)
        lineno = token.lineno
        return nodes.CallBlock(
            self.call_method(
                "_dict_set", [
                    nodes.Const(token.value, lineno=lineno),
                    parse_name_as_const(parser),
                    parse_keywords(parser),
                ],
                lineno=lineno
            ),
            [], [], [],
            lineno=lineno
        )

    def _dict_set(self, tpe, key, value, caller):
        target = getattr(self, tpe)
        if key in target:
            raise Exception()
        target[key] = value
        return ""

__all__ = (
    "AccountsExtension",
)
