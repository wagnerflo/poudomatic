from jinja2 import nodes
from jinja2.ext import Extension
from jinja2_rendervars import RenderVar

from .base import DispatchParseMixin

class BlockShortcuts(Extension):
    tags = frozenset([
        "portversion",
        "portrevision",
        "maintainer",
        "license",
    ])

    def parse(self, parser):
        token = next(parser.stream)
        lineno = token.lineno
        node = nodes.Block(lineno=lineno)
        node.name = token.value
        node.body = [
            nodes.Output([parser.parse_expression()], lineno=lineno)
        ]
        return node

class DescriptionExtension(DispatchParseMixin,Extension):
    tags = frozenset([
        "comment",
        "description",
        "www",
    ])
    comment = RenderVar("comment", None)
    description = RenderVar("description", None)
    www = RenderVar("www", None)

    def parse_description(self, parser, stream, token, lineno):
        return nodes.CallBlock(
            self.call_method("_description", [], lineno=lineno),
            [], [],
            parser.parse_statements(
                ("name:enddescription",), drop_needle=True
            ),
            lineno=lineno
        )

    def _description(self, caller):
        if self.description is not None:
            raise Exception()
        self.description = caller()
        return ""

    def parse_comment(self, parser, stream, token, lineno):
        node = nodes.Block(lineno=lineno)
        node.name = token.value
        node.body = [
            nodes.CallBlock(
                self.call_method(
                    "_comment",
                    [ parser.parse_expression() ],
                    lineno=lineno
                ),
                [], [], [], lineno=lineno
            )
        ]
        return node


    def _comment(self, value, caller):
        if self.comment is not None:
            raise Exception()
        self.comment = value
        return value

    def parse_www(self, parser, stream, token, lineno):
        return nodes.CallBlock(
            self.call_method(
                "_www", [ parser.parse_expression() ], lineno=lineno
            ),
            [], [], [], lineno=lineno
        )

    def _www(self, value, caller):
        if self.www is not None:
            raise Exception()
        self.www = value
        return ""

__all__ = (
    "BlockShortcuts",
    "DescriptionExtension",
)
