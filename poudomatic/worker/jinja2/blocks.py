from jinja2.ext import Extension
from jinja2.nodes import Block,Output,CallBlock

from .base import (
    DispatchParseMixin,
    load_from_context,
)

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
        node = Block(lineno=lineno)
        node.name = token.value
        node.body = [Output([parser.parse_expression()], lineno=lineno)]
        return node

class DescriptionExtension(DispatchParseMixin,Extension):
    tags = frozenset(["comment", "description"])

    def parse_description(self, parser, stream, token, lineno):
        return CallBlock(
            self.call_method(
                "_description", [load_from_context("metadata")],
                lineno=lineno
            ),
            [], [],
            parser.parse_statements(
                ("name:enddescription",), drop_needle=True
            ),
            lineno=lineno
        )

    def parse_comment(self, parser, stream, token, lineno):
        node = Block(lineno=lineno)
        node.name = token.value
        node.body = [
            CallBlock(
                self.call_method(
                    "_comment", [
                        load_from_context("metadata"),
                        parser.parse_expression(),
                    ], lineno=lineno
                ),
                [], [], [], lineno=lineno
            )
        ]
        return node

    def _description(self, metadata, caller):
        if metadata.description is not None:
            raise Exception()
        metadata.description = caller()
        return ""

    def _comment(self, metadata, value, caller):
        if metadata.comment is not None:
            raise Exception()
        metadata.comment = value
        return value

__all__ = (
    "BlockShortcuts",
    "DescriptionExtension",
)
