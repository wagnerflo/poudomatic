from abc import ABC,abstractmethod
from itertools import chain
from os import walk
from pathlib import Path
from re import compile as regex
from shutil import copytree
from urllib.parse import urlparse,urlunparse

from ..common import asyncinit,unblocked
from .port import Port

class Collection(ABC):
    _registry = []

    @classmethod
    def __init_subclass__(cls, /, scheme, **kwds):
        super().__init_subclass__(**kwds)
        cls._registry.append((regex(scheme), cls))

    @classmethod
    def new(cls, uri, path):
        uri = urlparse(uri)
        for re,cls in cls._registry:
            if re.match(uri.scheme):
                return cls.new(path, uri)

    def __init__(self, path):
        self.path = path

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

    @property
    @abstractmethod
    def uri(self):
        pass

    @property
    @abstractmethod
    def revision(self):
        pass

def mtime_walk(path):
    yield path.lstat().st_mtime
    for root,dirs,files in walk(path):
        for p in chain(dirs, files):
            yield Path(root, p).lstat().st_mtime

class LocalCollection(Collection, scheme=r"^file$"):
    @asyncinit
    @unblocked
    def new(self, uri):
        self._src = Path(uri.path).resolve()
        copytree(self._src, self.path, dirs_exist_ok=True)
        self._uri = self._src.as_uri()
        self._stamp = int(max(mtime_walk(self._src)))

    @property
    def uri(self):
        return self._uri

    @property
    def revision(self):
        return self._stamp
