from abc import ABC,abstractmethod
from asyncio import get_running_loop
from jinja2 import Environment,PackageLoader
from jinja2_rendervars import RenderVarsExtension

from ..common import unblocked
from .jinja2 import *

class BaseRuntime(ABC):
    @classmethod
    @abstractmethod
    async def new(cls, loader):
        self = cls()
        self.jinja2 = Environment(
            loader = loader,
            extensions = (
                BlockShortcuts,
                DependsExtension,
                DescriptionExtension,
                FiltersExtension,
                InstallExtension,
                RenderVarsExtension,
                ScriptExtension,
            ),
            autoescape = False,
            line_statement_prefix = '%',
            line_comment_prefix = '##',
            keep_trailing_newline = True,
        )
        return self

    def render_port(self, template, target, **context):
        tmpl = self.jinja2.from_string(template.read_text())
        with target.open('w') as fp:
            with self.jinja2.rendervars() as vars:
                tmpl.stream(context).dump(fp)
                return vars

    def render_template(self, name, target, **context):
        tmpl = self.jinja2.get_template(name)
        with target.open('w') as fp:
            tmpl.stream(context).dump(fp)

    @abstractmethod
    async def log(self, msg):
        pass

class ConsoleRuntime(BaseRuntime):
    @classmethod
    async def new(cls):
        return await super().new(
            loader = PackageLoader('poudomatic.common', 'templates'),
        )

    async def log(self, msg):
        print(msg)
