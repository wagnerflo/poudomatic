from jinja2 import nodes
from jinja2.ext import Extension
from shlex import quote as shquote

class BlockShortcuts(Extension):
    tags = frozenset([
        "portversion",
    ])

    def parse(self, parser):
        token = next(parser.stream)
        lineno = token.lineno
        node = nodes.Block(lineno=lineno)
        node.name = token.value
        node.body = [nodes.Output([parser.parse_expression()], lineno=lineno)]
        return node

class InstallExtension(Extension):
    tags = frozenset([
        "install",
        "substitute",
    ])

    def parse(self, parser):
        stream = parser.stream
        token = next(stream)
        return getattr(self, f"parse_{token.value}")(
            parser, stream, token, token.lineno
        )

    def parse_install(self, parser, stream, token, lineno):
        tpe = stream.expect("name").value
        args = list(
            getattr(self, f"parse_install_{tpe}")(parser, stream, lineno)
        )
        return nodes.CallBlock(
            self.call_method(
                "_install",
                [nodes.ContextReference(), nodes.Const(tpe)] + args,
                lineno=lineno
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

    def _install(self, ctx, tpe, src, dst, patterns, caller):
        metadata = ctx["metadata"]
        metadata.install.append((
            tpe, src, dst, patterns or []
        ))
        metadata.plist.append(dst)
        return ""

class ShellEscapeExtension(Extension):
    def __init__(self, environment):
        super().__init__(environment)
        environment.filters["shquote"] = self._shquote

    def _shquote(self, s):
        return shquote(str(s))

__all__ = (
    "BlockShortcuts",
    "InstallExtension",
    "ShellEscapeExtension",
)
