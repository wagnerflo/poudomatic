from git.repo.base import Repo as GitRepo
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse
from lzma import LZMAFile,FORMAT_XZ,CHECK_SHA256

from .config import load_poudomatic
from . import poudriere

class Repository:
    def __init__(self, url, config_context):
        self.url = url
        try:
            self.packages = load_poudomatic(self._path, config_context)
        except FileNotFoundError:
            raise Exception()

    @classmethod
    def clone_from_url(cls, url, config_context):
        scheme = urlparse(url).scheme
        for cls in cls.__subclasses__():
            if scheme.startswith(cls.scheme_prefix):
                return cls(url, config_context)

        raise Exception()

    def __contains__(self, key):
        return key in self.packages

    def __getitem__(self, key):
        return self.packages[key]

    def generate_distfile(self):
        raise NotImplementedError()

class GitRepository(Repository):
    scheme_prefix = 'git+'

    def __init__(self, url, config_context):
        self._tempdir = TemporaryDirectory()
        self._path = Path(self._tempdir.name)
        self._repo = GitRepo.clone_from(url[4:], self._tempdir.name)
        super().__init__(url, config_context)

    def generate_distfile(self):
        hexsha = self._repo.head.commit.hexsha
        filename = poudriere.DISTFILES / '{}.txz'.format(hexsha)

        if not filename.exists():
            with LZMAFile(filename, 'w', preset=9,
                          format=FORMAT_XZ, check=CHECK_SHA256) as fp:
                self._repo.archive(fp, hexsha)

        return filename
