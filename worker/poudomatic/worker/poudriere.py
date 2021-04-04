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

BulkStats = namedtuple("BulkStats", (
    "pkgmap",
    "depends",
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

    def bulk(self, *args, logger):
        errors = []
        try:
            with self("bulk", *args) as proc:
                for line in proc:
                    line = line.rstrip()
                    if logger:
                        logger.info(line)
                    _,_,msg = line.partition("Error: ")
                    if msg:
                        errors.append(msg)
        except CommandError:
            return errors

    def clean_logs(self, with_task=False):
        for root,dirs,files in walk_dir(self.path_logs):
            root = Path(root)
            for item in { self.task_id if with_task else None, "assets",
                          ".html", "latest-per-pkg" }.intersection(dirs):
                rmtree(root / item)
                dirs.remove(item)
            for item in { ".data.json", ".data.mini.json", "index.html",
                          "build.html", "robots.txt", }.intersection(files):
                (root / item).unlink()
            for item in { "latest", "latest-done" }.intersection(dirs):
                (root / item).unlink()

    def read_bulk_stats(self):
        base = next(self.path_logs.glob(f"bulk/*/{self.task_id}"))
        pkgmap = {}
        depends = defaultdict(set)
        built = set()

        with (base / ".poudriere.all_pkgs%").open() as fp:
            for line in fp:
                pkg,origin,*_ = line.strip().split()
                pkgmap[pkg] = origin

        with (base / ".poudriere.pkg_deps%").open() as fp:
            for line in fp:
                pkg,dep = line.strip().split()
                depends[pkgmap[pkg]].add(pkgmap[dep])

        with (base / ".poudriere.ports.built").open() as fp:
            for line in fp:
                _,pkg,*_ = line.strip().split()
                built.add(pkg)

        return BulkStats(pkgmap, dict(depends), built)

class PoudriereJail:
    def __init__(self, name):
        self.name = name
        self.path = Path(
            process("jls", "-j", self.name, "path").run().strip()
        )

    def exec(self, *args):
        return process("jexec", self.name, *args)
