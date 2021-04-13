from jinja2 import nodes
from jinja2.ext import Extension
from jinja2_rendervars import RenderVar
from types import SimpleNamespace

from .base import (
    DispatchParseMixin,
    parse_name_as_const,
)

class VerifyExtension(DispatchParseMixin,Extension):
    tags = frozenset(["verify"])

    @RenderVar("verify")
    def verify():
        return SimpleNamespace(how = None)

    def parse_verify(self, parser, stream, token, lineno):
        tpe = parse_name_as_const(parser)
        return nodes.CallBlock(
            self.call_method(
                f"_set_{tpe.value}",
                list(
                    self.dispatch(
                        f"parse_{tpe.value}",
                        parser, stream, lineno
                    )
                ), lineno=lineno
            ),
            [], [], [], lineno=lineno
        )

    def parse_gpg(self, parser, stream, lineno):
        yield parser.parse_expression()

    def _set_gpg(self, fingerprint, caller):
        if self.verify.how is not None:
            raise Exception()
        self.verify.how = "gpg"
        self.verify.fingerprint = fingerprint
        return ""

__all__ = (
    "VerifyExtension",
)
