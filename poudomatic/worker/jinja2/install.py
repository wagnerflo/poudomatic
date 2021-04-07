from jinja2 import nodes
from jinja2.ext import Extension

from .base import (
    DispatchParseMixin,
    load_from_context,
)

class InstallExtension(DispatchParseMixin,Extension):
    tags = frozenset([
        "install",
        "substitute",
    ])

    def parse_install(self, parser, stream, token, lineno):
        tpe = stream.expect("name").value
        return nodes.CallBlock(
            self.call_method(
                "_install", [
                    load_from_context("metadata", "install"),
                    load_from_context("metadata", "plist"),
                    nodes.Const(tpe),
                    *self.dispatch(
                        f"parse_install_{tpe}", parser, stream, lineno
                    )
                ], lineno=lineno
            ),
            [], [], [], lineno=lineno
        )

    def parse_install_script(self, parser, stream, lineno):
        yield parser.parse_expression()
        stream.expect("name:as")
        yield parser.parse_expression()
        yield nodes.Name("_patterns", "load", lineno=lineno)

    def parse_install_data(self, parser, stream, lineno):
        return self.parse_install_script(parser, stream, lineno)

    def parse_install_symlink(self, parser, stream, lineno):
        stream.expect("name:to")
        yield parser.parse_expression()
        stream.expect("name:as")
        yield parser.parse_expression()
        yield nodes.Const(None)

    def parse_substitute(self, parser, stream, token, lineno):
        node = nodes.With(lineno=lineno)
        patterns = []

        if stream.current.type == "lbrace":
            end = "rbrace"
            next(stream)
        else:
            end = "block_end"

        while stream.current.type != end:
            if patterns:
                stream.expect("comma")
            pattern = parser.parse_expression()
            stream.expect("name:with")
            replacement = parser.parse_expression()
            patterns.append(
                nodes.Tuple([pattern, replacement], "store", lineno=lineno)
            )

        if end != "block_end":
            stream.expect(end)

        return nodes.With(
            [nodes.Name("_patterns", "param", lineno=lineno)],
            [nodes.List(patterns, lineno=lineno)],
            parser.parse_statements(
                ("name:endsubstitute",), drop_needle=True
            ),
            lineno=lineno
        )

    def _install(self, install, plist, tpe, src, dst, patterns, caller):
        install.append((tpe, src, dst, patterns or []))
        plist.append(dst)
        return ""

__all__ = (
    "InstallExtension",
)
