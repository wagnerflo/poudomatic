from collections import defaultdict,OrderedDict
from dataclasses import dataclass,field,InitVar as initvar
from functools import cmp_to_key
from .libpkg import pkg_version_cmp,pkg_create_repo

@dataclass(frozen=True, init=False)
class PkgParts:
    name: str
    version: str
    fullversion: str
    revision: str
    epoch: str

    def __init__(self, pkgname):
        name,fullversion = pkgname.rsplit('-', 1)
        version,*rest = fullversion.rsplit('_', 1)
        revision = None
        epoch = None
        if rest:
            revision,*rest = rest[0].rsplit(',', 1)
            if rest:
                epoch = rest[0]

        object.__setattr__(self, 'name', name)
        object.__setattr__(self, 'version', version)
        object.__setattr__(self, 'fullversion', fullversion)
        object.__setattr__(self, 'revision', revision)
        object.__setattr__(self, 'epoch', epoch)

version_key = cmp_to_key(pkg_version_cmp)

def sorted_by_version(iterable, reverse=False):
    return sorted(iterable, version_key, reverse)

def index_pkg_paths(iterable):
    res = defaultdict(list)
    for item in iterable:
        parts = PkgParts(item.stem)
        res[parts.name].append((parts.fullversion, item))
    ret = {}
    for key,lst in res.items():
        lst.sort(key=lambda item: version_key(item[0]), reverse=True)
        ret[key] = OrderedDict(lst)
    return ret
