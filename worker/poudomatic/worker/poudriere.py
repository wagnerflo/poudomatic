from collections import defaultdict,namedtuple
from contextlib import contextmanager
from os import walk as walk_dir
from pathlib import Path
from shutil import rmtree
from tempfile import TemporaryDirectory

from .util import (
    zfs,
    process,
    shquote,
    CommandError,
)
from . import files

PkgDeps = namedtuple("PkgDeps", (
    "pkgmap",
    "depends",
))

BulkStats = namedtuple("BulkStats", (
    "built"
))

class Poudriere:
    def __init__(self, dset, task_id):
        self.zpool,sep,self.zrootfs = dset.name.partition("/")
        self.zrootfs = f"{sep}{self.zrootfs}"
        self.task_id = task_id
        self.path_basefs = Path(dset.mountpoint)
        self.path_logs = self.path_basefs / "logs"

    def __enter__(self):
        self.path           = TemporaryDirectory()
        self.path_conf      = Path(self.path.name) / "poudriere.conf"
        self.path_d         = Path(self.path.name) / "poudriere.d"
        self.path_jails_d   = self.path_d / "jails"
        self.path_ports_d   = self.path_d / "ports"
        self.path_make_conf = self.path_d / "make.conf"

        self.path_d.mkdir()
        files.template_to_file(
            "poudriere.conf", self.path_conf,
            ZPOOL   = self.zpool,
            ZROOTFS = self.zrootfs,
            BASEFS  = str(self.path_basefs),
            TASK_ID = self.task_id,
        )

        self.cmd = ("/usr/local/bin/poudriere", "-e", self.path.name)
        return self

    def __exit__(self, ex_type, ex_value, ex_tb):
        self.path.cleanup()
        for root,dirs,files in walk_dir(self.path_logs):
            root = Path(root)
            for item in { "assets", ".html", "latest-per-pkg",
                          self.task_id }.intersection(dirs):
                rmtree(root / item)
                dirs.remove(item)
            for item in { ".data.json", ".data.mini.json", "index.html",
                          "build.html", "robots.txt", }.intersection(files):
                (root / item).unlink()
            for item in { "latest", "latest-done" }.intersection(dirs):
                (root / item).unlink()

    def __call__(self, *args):
        return process(*self.cmd + args)

    def api(self, *stdin):
        return self("api") << stdin

    def _prop_set(self, func, name, **props):
        self.api(
            f"{func} {shquote(name, prop, value)}"
            for prop,value in props.items()
        ).run()

    def register_ports(self, portstree, mountpoint):
        self._prop_set(
            "pset", portstree.name,
            mnt=mountpoint,
            timestamp=portstree.timestamp,
            method="null",
        )

    def register_jail(self, jail):
        self._prop_set(
            "jset", jail.name,
            mnt=jail.mountpoint,
            arch="amd64",
            version=jail.version.longname,
            method="null",
        )

    @contextmanager
    def jail(self, jailname, portstree):
        self("jail", "-s", "-j", jailname, "-p", portstree).run()
        try:
            yield PoudriereJail(f"{jailname}-{portstree}")
        finally:
            self("jail", "-k", "-j", jailname, "-p", portstree).run()

    def bulk(self, *args, logfunc=None):
        errors = []
        try:
            with self("bulk", *args) as proc:
                for line in proc:
                    line = line.rstrip()
                    if logfunc:
                        logfunc(line)
                    _,_,msg = line.partition("Error: ")
                    if msg:
                        errors.append(msg)
        except CommandError:
            return errors

    def get_logbase(self, jail, portsbranch):
        return (
            self.path_logs / "bulk" / f"{jail}-{portsbranch}" /
            self.task_id
        )

    def get_buildlogbase(self, jail, portsbranch):
        return self.get_logbase(jail, portsbranch) / "logs"

    def read_pkg_deps(self , jail, portsbranch):
        base = self.get_logbase(jail, portsbranch)
        all_pkgs = base / ".poudriere.all_pkgs%"
        pkg_deps = base / ".poudriere.pkg_deps%"

        pkgmap = {}
        depends = defaultdict(set)

        if all_pkgs.exists() and pkg_deps.exists():
            with all_pkgs.open() as fp:
                for line in fp:
                    pkg,origin,*_ = line.strip().split()
                    pkgmap[pkg] = origin

            with pkg_deps.open() as fp:
                for line in fp:
                    pkg,dep = line.strip().split()
                    depends[pkgmap[pkg]].add(pkgmap[dep])

        return PkgDeps(pkgmap, dict(depends))

    def read_bulk_stats(self, jail, portsbranch):
        base = self.get_logbase(jail, portsbranch)
        ports_built = base / ".poudriere.ports.built"

        built = set()

        if ports_built.exists():
            with ports_built.open() as fp:
                for line in fp:
                    _,pkg,*_ = line.strip().split()
                    built.add(pkg)

        return BulkStats(built)

class PoudriereJail:
    def __init__(self, name):
        self.name = name
        self.path = Path(
            process("jls", "-j", self.name, "path").run().strip()
        )

    def exec(self, *args):
        return process("jexec", self.name, *args)
