from jinja2.ext import Extension
from jinja2.nodes import Block,Output

class BlockShortcuts(Extension):
    tags = frozenset([
        "portversion",
        "portrevision",
        "maintainer",
    ])

    def parse(self, parser):
        token = next(parser.stream)
        lineno = token.lineno
        node = Block(lineno=lineno)
        node.name = token.value
        node.body = [Output([parser.parse_expression()], lineno=lineno)]
        return node

__all__ = (
    "BlockShortcuts",
)
