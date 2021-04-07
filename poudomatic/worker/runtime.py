from abc import ABC,abstractmethod
from asyncio import get_running_loop
from jinja2 import Environment,PackageLoader

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
                FiltersExtension,
                InstallExtension,
            ),
            autoescape = False,
            line_statement_prefix = '%',
            line_comment_prefix = '##',
            keep_trailing_newline = True,
        )
        return self

    def get_template(self, path):
        return self.jinja2.from_string(path.read_text())

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
