from jinja2 import nodes
from jinja2.ext import Extension
from jinja2.exceptions import TemplateSyntaxError
from jinja2.lexer import describe_token

from .base import (
    parse_strings,
    load_from_context,
)

class Dependency:
    def __init__(self, origin, version, uri):
        self.origin = origin
        self.version = version or [('>', '0')]
        self.uri = uri
        self.is_external = uri is None
        self.category,_,self.portname = self.origin.partition("/")
        self.DEPENDS = (
            f"{self.portname}"
            f"{''.join(s+v for s,v in self.version)}:"
            f"{self.origin}"
        )

class DependsExtension(Extension):
    tags = frozenset([
        "run_depends",
    ])

    def parse(self, parser):
        stream = parser.stream
        token = next(stream)
        lineno = token.lineno

        tpe = token.value
        origin = parse_strings(parser)
        version = nodes.List([], lineno=origin.lineno)

        # up to two version modifier allowd
        for _ in range(2):
            if stream.current.type not in ("assign", "eq", "gt", "gteq", "lt", "lteq"):
                break

            token = next(stream)
            version.items.append(
                nodes.Tuple([
                    nodes.Const(token.value, lineno=token.lineno),
                    parse_strings(parser),
                ], "store", lineno=lineno)
            )

        # reference to port definied in same collection,
        if stream.current.test("name:local"):
            next(stream)
            collection = load_from_context("collection", "uri")

        # to port from remote collection or
        elif stream.current.test("name:from"):
            next(stream)
            collection = parse_strings(parser)

        # to port from portstree
        elif stream.current.type == "block_end":
            collection = nodes.Const(None, lineno=stream.current.lineno)

        else:
            raise TemplateSyntaxError(
                f"unexpected token {describe_token(token)!r}",
                token.lineno, stream.name, stream.filename,
            )

        return nodes.CallBlock(
            self.call_method(
                "_depends", [
                    load_from_context("metadata", tpe),
                    origin, version, collection,

                ], lineno=lineno
            ),
            [], [], [], lineno=lineno
        )

    def _depends(self, depends, origin, version, collection, caller):
        depends.append(Dependency(origin, version, collection))
        return ""

__all__ = (
    "DependsExtension",
)
