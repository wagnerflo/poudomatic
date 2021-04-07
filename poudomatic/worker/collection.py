from abc import ABC,abstractmethod
from pathlib import Path
from re import compile as regex
from shutil import copytree
from urllib.parse import urlparse,urlunparse

from ..common import ainit,unblocked
from .port import Port

class Collection(ABC):
    _registry = []

    @classmethod
    def __init_subclass__(cls, /, scheme, **kwds):
        super().__init_subclass__(**kwds)
        cls._registry.append((regex(scheme), cls))

    @classmethod
    def new(cls, uri, targetdir):
        uri = urlparse(uri)
        for re,cls in cls._registry:
            if re.match(uri.scheme):
                return cls.new(uri, targetdir)

    @unblocked
    def __aiter__(self):
        for template in (self.path / "poudomatic").glob("*.tmpl"):
            category,_,portname = template.stem.partition("_")
            yield Port(category, portname, template, self)

    @unblocked
    def get_port(self, category, portname):
        template = self.path / "poudomatic" / f"{category}_{portname}.tmpl"
        if not template.is_file():
            raise Exception()
        return Port(category, portname, template, self)

class LocalCollection(Collection, scheme=r"^file$"):
    @ainit
    @unblocked
    def new(self, uri, targetdir):
        print("LocalCollection.new")
        self.src = Path(uri.path).resolve()
        self.path = copytree(self.src, targetdir, dirs_exist_ok=True)
        self.uri = self.src.as_uri()
