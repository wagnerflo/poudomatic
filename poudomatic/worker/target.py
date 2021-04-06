from abc import ABC,abstractmethod
from contextlib import AsyncExitStack
from pathlib import Path
from re import compile as regex
from urllib.parse import urlparse,urlunparse

from ..common import (
    abspath,
    temp_copy,
    to_thread,
    max_mtime,
)

class Target(ABC):
    _registry = []

    @classmethod
    async def fetch(cls, uri, tempdir):
        uri = urlparse(uri)
        for re,cls in cls._registry:
            if re.match(uri.scheme):
                return await cls.new(uri, tempdir)
        raise Exception()

    @classmethod
    def __init_subclass__(cls, /, scheme, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._registry.append((regex(scheme), cls))

    @classmethod
    async def new(cls, uri):
        self = cls()
        self.uri = uri
        self.key = urlunparse(self.uri)
        self.exit_stack = AsyncExitStack()
        return self

    async def with_context(self, cm):
        return await self.exit_stack.enter_async_context(cm)

    async def cleanup(self):
        await self.exit_stack.aclose()

    @to_thread
    def templates(self):
        return list((self.path / "poudomatic").glob("*.tmpl"))

class FileTarget(Target, scheme=r"^file$"):
    @classmethod
    async def new(cls, uri, tempdir):
        self = await super().new(uri)
        self.src = Path(await abspath(uri.path))
        self.path = await self.with_context(
            temp_copy(self.src, dir=tempdir, ignore_errors=True)
        )
        self.key = self.src.as_uri()
        self.timestamp = await max_mtime(self.src)
        return self
