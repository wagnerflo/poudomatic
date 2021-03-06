from collections import namedtuple
from jinja2 import nodes
from jinja2.ext import Extension
from jinja2.exceptions import TemplateSyntaxError
from jinja2.lexer import describe_token
from jinja2_rendervars import RenderVar

from .base import (
    DispatchParseMixin,
    parse_name_as_const,
    make_default,
    make_dict,
)

InstallItem = namedtuple("InstallItem", ("type", "src", "dest", "conf"))

class InstallExtension(DispatchParseMixin,Extension):
    tags = frozenset([
        "install",
        "mkdir",
        "substitute",
    ])

    install = RenderVar("install", list)

    def make_install(self, parser, stream, token, lineno, *args):
        return nodes.CallBlock(
            self.call_method("_install", list(args), lineno=lineno),
            [], [], [], lineno=lineno
        )

    def parse_install(self, parser, stream, token, lineno):
        tpe = parse_name_as_const(parser)
        return self.make_install(
            parser, stream, token, lineno,
            tpe, *self.dispatch(
                f"parse_install_{tpe.value}",
                parser, stream, lineno
            )
        )

    def parse_mkdir(self, parser, stream, token, lineno):
        dst = parser.parse_expression()
        conf = {}
        conf_keys = set(("mode", "user", "group"))

        while stream.current.type != "block_end":
            token = stream.expect("name")
            if token.value not in conf_keys:
                raise TemplateSyntaxError(
                    f"unexpected token {describe_token(token)!r}",
                    token.lineno, stream.name, stream.filename,
                )
            conf[token.value] = parser.parse_expression()

        return self.make_install(
            parser, stream, token, lineno,
            nodes.Const("mkdir", lineno=lineno),
            nodes.Const(None, lineno=lineno),
            dst,
            nodes.Const("@dir", lineno=lineno),
            make_dict(conf, lineno=lineno),
        )

    def parse_install_script(self, parser, stream, lineno):
        yield parser.parse_expression()
        stream.expect("name:as")
        yield parser.parse_expression()
        yield nodes.Const(None, lineno=lineno)
        yield self.make_patterns(lineno)

    def parse_install_data(self, parser, stream, lineno):
        return self.parse_install_script(parser, stream, lineno)

    def parse_install_symlink(self, parser, stream, lineno):
        stream.expect("name:to")
        yield parser.parse_expression()
        stream.expect("name:as")
        yield parser.parse_expression()
        yield nodes.Const(None, lineno=lineno)
        yield nodes.Const(None, lineno=lineno)

    def parse_install_man(self, parser, stream, lineno):
        yield parser.parse_expression()
        stream.expect("name:into")
        stream.expect("name:section")
        section = stream.expect("integer")
        yield nodes.Const(section.value, lineno=section.lineno)
        yield nodes.Const(None, lineno=lineno)
        yield self.make_patterns(lineno)

    def make_patterns(self, lineno):
        return make_dict({
            "patterns": make_default(
                nodes.Name("_patterns", "load", lineno=lineno),
                nodes.Const(None, lineno=lineno)
            )
        }, lineno=lineno)

    def parse_substitute(self, parser, stream, token, lineno):
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

    def _install(self, tpe, src, dst, keyword, conf, caller):
        self.install.append(InstallItem(tpe, src, dst, conf))
        return ""

__all__ = (
    "InstallExtension",
)
