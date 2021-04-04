from configparser import ConfigParser
from contextlib import contextmanager
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory

from .util import zfs
from .poudriere import Poudriere
from .versions import *

class Environment:
    PROPERTY = "poudomatic:environment"
    VERSION = 1

    DATASETS = (
        ( ".m",        None            ),
        ( "cache",     None            ),
        ( "ccache",    zfs.COMPRESSION ),
        ( "distfiles", None            ),
        ( "etc",       zfs.COMPRESSION ),
        ( "jails",     zfs.COMPRESSION ),
        ( "logs",      None            ),
        ( "packages",  None            ),
        ( "ports",     zfs.COMPRESSION ),
        ( "src",       zfs.COMPRESSION ),
        ( "wrkdirs",   None            ),
    )

    def __init__(self, dataset):
        if (dset := zfs.get_dataset(dataset)) is None:
            raise Exception(f"ZFS dataset '{dataset}' doesn't exist.")

        if not zfs.is_filesystem(dset):
            raise Exception(f"ZFS dataset '{dataset}' is no filesystem.")

        if dset.mountpoint is None:
            raise Exception(f"ZFS dataset '{dataset}' is not mounted.")

        self.dset = dset
        self.path = Path(dset.mountpoint)

        if (version := zfs.get_property(dset, self.PROPERTY)) is None:
            self.setup()
        else:
            self.upgrade(int(version))

        self.dset_jails = zfs.get_dataset(f"{dataset}/jails")
        self.dset_ports = zfs.get_dataset(f"{dataset}/ports")
        self.dset_pkgs = zfs.get_dataset(f"{dataset}/packages")
        self.dset_src = zfs.get_dataset(f"{dataset}/src")
        self.etc_path = self.path / "etc"
        self.packages_path = Path(
            zfs.get_dataset(f"{dataset}/packages").mountpoint
        )

    def get_config(self, section, key):
        conf = ConfigParser(
            interpolation=None,
            strict=False,
            empty_lines_in_values=False,
        )
        conf.read(self.etc_path / "poudomatic.conf")
        return conf.get(section, key)

    def setup(self):
        if list(self.dset.children):
            raise Exception(
                f"ZFS dataset '{self.dset.name}' has children: "
                f"Setup impossible."
            )

        if list(self.path.iterdir()):
            raise Exception(
                f"ZFS dataset '{self.dset.name}' is not empty: "
                f"Setup impossible."
            )

        # disable compression and atime on root dataset
        zfs.set_properties(self.dset, zfs.NOCOMPRESSION + zfs.NOATIME)

        # create child datasets
        for name,props in self.DATASETS:
            zfs.create_dataset(f"{self.dset.name}/{name}", props)

        # set properties
        zfs.set_properties(self.dset, {
            self.PROPERTY:    self.VERSION,
            "poudriere:type": "data",
        })

    def upgrade(self, old_version):
        for ver in range(old_version + 1, self.VERSION + 1):
            getattr(self, f"upgrade_to_{ver}")()

    def get_poudriere(self, task_id):
        return Poudriere(self.dset, task_id)

    def get_ports(self, branch):
        dset = f"{self.dset_ports.name}/{branch.name}"
        if snap := zfs.get_newest_snapshot(dset):
            return PortsTree(snap)

    def get_jail(self, version):
        dset = f"{self.dset_jails.name}/{version.shortname}"
        if (dset := zfs.get_dataset(dset)) is not None:
            return Jail(dset)

    def get_packages(self, jail, branch):
        name = f"{self.dset_pkgs.name}/{jail.shortname}-{branch.name}"
        if (dset := zfs.get_dataset(name)) is None:
            dset = zfs.create_dataset(name)
        return Packages(dset)


class Jail:
    def __init__(self, dset):
        self.dset = dset
        _,_,self.version = dset.name.rpartition("/")
        self.version = FreeBSDVersion.parse_str(self.version)

    @property
    def mountpoint(self):
        return self.dset.mountpoint

    @property
    def name(self):
        return self.version.shortname


class PortsTree:
    def __init__(self, snap):
        self.snap = snap
        _,_,self.branch = snap.name.rpartition("/")
        self.branch,_,self.timestamp = self.branch.rpartition("@")
        self.branch = PortsBranchVersion.parse_str(self.branch)

    @property
    def name(self):
        return self.branch.name

    @contextmanager
    def clone(self):
        with zfs.temp_clone(self.snap) as dset:
            yield dset


class Packages:
    def __init__(self, dset):
        self.dset = dset

    @property
    def mountpoint(self):
        return Path(self.dset.mountpoint)

    @contextmanager
    def transaction(self):
        with zfs.temp_snapshot(self.dset) as snap:
            try:
                yield snap
            except:
                zfs.rollback_snapshot(snap)
                raise
