from jinja2 import nodes
from jinja2.ext import Extension
from jinja2.exceptions import TemplateSyntaxError
from jinja2.lexer import describe_token
from jinja2_rendervars import RenderVar

from .base import (
    load_from_context,
    parse_name_as_const,
    parse_token_as_const,
)

class Dependency:
    def __init__(self, origin, modifier, version, uri, portname=None):
        self.origin = origin
        self.modifier = modifier
        self.version = [(s, str(v)) for s,v in version] or [(">", "0")]
        self.uri = uri
        self.is_external = uri is None
        self.category,_,pn = self.origin.partition("/")
        self.portname = portname if portname else pn
        self.DEPENDS = (
            f"{self.portname}"
            f"{''.join(s+v for s,v in self.version)}:"
            f"{self.origin}"
        )

class DependsExtension(Extension):
    tags = frozenset([
        "build_depends",
        "run_depends",
    ])

    @RenderVar("depends", tags=tags)
    def depends(tags):
        return { tag: [] for tag in tags }

    def parse(self, parser):
        stream = parser.stream
        lineno = stream.current.lineno

        modifier = nodes.Const(None, lineno=lineno)
        portname = nodes.Const(None, lineno=lineno)

        tpe = parse_name_as_const(parser)

        for opt in ("python",):
            if stream.current.test(f"name:{opt}"):
                modifier = nodes.Const(opt, lineno=next(stream).lineno)
                break

        origin = parser.parse_expression()
        version = nodes.List([], lineno=origin.lineno)

        # up to two version modifiers allowed
        if stream.current.test("name:version"):
            next(stream)
            for i in range(2):
                if stream.current.type not in ("assign", "eq", "gt", "gteq", "lt", "lteq"):
                    break
                version.items.append(
                    nodes.Tuple([
                        parse_token_as_const(parser),
                        parser.parse_expression(),
                    ], "store", lineno=lineno)
                )
                if stream.current.test("comma"):
                    next(stream)

        # portname override
        if stream.current.test("name:portname"):
            next(stream)
            portname = parser.parse_expression()

        # reference to port definied in same collection,
        if stream.current.test("name:local"):
            next(stream)
            collection = load_from_context("collection", "uri")

        # to port from remote collection or
        elif stream.current.test("name:from"):
            next(stream)
            collection = parser.parse_expression()

        # to port from portstree
        elif stream.current.type == "block_end":
            collection = nodes.Const(None, lineno=stream.current.lineno)

        else:
            raise TemplateSyntaxError(
                f"unexpected token {describe_token(stream.current)!r}",
                stream.current.lineno, stream.name, stream.filename,
            )

        return nodes.CallBlock(
            self.call_method(
                "_depends",
                [ tpe, modifier, origin, version, portname, collection ],
                lineno=lineno
            ),
            [], [], [], lineno=lineno
        )

    def _depends(self, tpe, modifier, origin, version, portname, collection, caller):
        self.depends[tpe].append(
            Dependency(origin, modifier, version, collection, portname=portname)
        )
        return ""

__all__ = (
    "DependsExtension",
)
