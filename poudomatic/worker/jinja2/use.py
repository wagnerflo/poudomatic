from collections import namedtuple
from jinja2 import nodes
from jinja2.ext import Extension
from jinja2_rendervars import RenderVar

from .base import (
    parse_name_as_const,
    parse_keywords,
    make_default,
    make_dict,
)

class UseExtension(Extension):
    tags = frozenset(["use"])

    def parse(self, parser):
        stream = parser.stream
        token = next(stream)

        macro = stream.expect("name").value
        stream.expect("name:from")
        template = stream.expect("name").value

        stream.expect("name:with")
        lineno = stream.expect("lbrace").lineno
        context = nodes.With(
            [], [], [
                nodes.FromImport(
                    nodes.Const(f"use/{template}", lineno=lineno),
                    [macro], True, lineno=lineno
                ),
                nodes.Output(
                    [ nodes.Call(
                          nodes.Name(macro, "load"),
                          [], [], None, None,
                          lineno=lineno
                      ) ],
                    lineno=lineno
                )
            ],
            lineno=lineno
        )
        while stream.current.type != "rbrace":
            token = stream.expect("name")
            context.targets.append(
                nodes.Name(token.value, "param", lineno=token.lineno)
            )
            parser.stream.expect("assign")
            context.values.append(
                parser.parse_expression()
            )
            if stream.current.test("comma"):
                next(stream)

        lineno = next(stream).lineno
        return nodes.Macro(
            macro, [], [], [context], lineno=lineno
        )

__all__ = (
    "UseExtension",
)
