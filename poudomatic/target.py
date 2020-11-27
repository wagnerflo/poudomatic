from os.path import relpath
from pathlib import Path
from shutil import copy as copy_file
from tempfile import TemporaryDirectory

from . import pkg
from . import poudriere
from . import zfs

class Jail:
    def __init__(self, name):
        self.name = name
        self.mnt = poudriere.jailmnt(name)
        self.clean = poudriere.jailclean(name)

    def clone(self):
        return ClonedJail(self.name)

class ClonedJail(Jail):
    def __init__(self, srcname):
        self.tempdir = TemporaryDirectory(dir=poudriere.JAILSD)
        self.name = Path(self.tempdir.name).name
        self.mnt = poudriere.JAILS_BASE / self.name
        snap = poudriere.jailclean(srcname)
        self.clone = zfs.TemporaryClone(
            snap,
            '{}/{}'.format(snap.parent.name, self.name),
            mountpoint=str(self.mnt),
        )
        self.clone.mount()
        self.clean = zfs.create_snapshot(self.clone.fs, 'clean')
        poudriere.clone_jail(
            srcname, self.name,
            fs=self.clone.fs.name,
            mnt=str(self.mnt),
            method='null',
        )

class Ports:
    def __init__(self, name):
        self.name = name
        self.mnt = poudriere.portsmnt(name)

    def clone(self):
        return ClonedPorts(self.name)

class ClonedPorts(Ports):
    def __init__(self, srcname):
        self.tempdir = TemporaryDirectory(dir=poudriere.PORTSD)
        self.name = Path(self.tempdir.name).name
        self.mnt = poudriere.PORTS_BASE / self.name
        self.clone = zfs.TemporaryClone(
            poudriere.portsfs(srcname),
            '{}/{}'.format(poudriere.PORTS_FS.name, self.name),
            mountpoint=str(self.mnt)
        )
        self.clone.mount()
        poudriere.clone_ports(
            srcname, self.name,
            method='null',
            mnt=str(self.mnt),
        )

class Repo:
    def __init__(self, name):
        self.name = name
        self.fs = zfs.get_dataset(name)
        self.mnt = Path(self.fs.mountpoint)
        self.all_directory = self.mnt / 'All'
        self.latest_directory = self.mnt / 'Latest'
        self.lockfile = self.mnt / '.poudomatic.lock'
        self.meta_file = self.mnt / 'meta.conf'

    def clone(self, mnt):
        return ClonedRepo(self.name, mnt)

    @property
    def all_packages(self):
        return self.all_directory.glob('*.txz')

    def add_package(self, path):
        self.all_directory.mkdir(exist_ok=True)
        copy_file(str(path), str(self.all_directory))

    def refresh_catalogue(self, rsa_key=None, password_cb=None):
        if not self.meta_file.exists():
            meta_file = None
        else:
            meta_file = str(self.meta_file)
        if rsa_key is not None:
            rsa_key = str(rsa_key)
        pkg.pkg_create_repo(
            str(self.mnt), meta_file=meta_file,
            rsa_key=rsa_key, password_cb=password_cb,
        )

        self.latest_directory.mkdir(exist_ok=True)
        for pkgname,versions in pkg.index_pkg_paths(self.all_packages).items():
            target = next(iter(versions.values()))
            latest = self.latest_directory / '{}.txz'.format(pkgname)
            latest.unlink(missing_ok=True)
            latest.symlink_to(relpath(str(target), str(latest.parent)))

class ClonedRepo(Repo):
    def __init__(self, srcname, mnt):
        src = zfs.get_dataset(srcname)
        name = '{}/{}'.format(srcname, mnt.name)
        self.clone = zfs.TemporaryClone(
            src, name,
            mountpoint=str(mnt)
        )
        self.clone.mount()
        super().__init__(name)

class Target:
    def __init__(self, jail, ports, repo):
        self.jail = Jail(jail)
        self.ports = Ports(ports)
        self.repo = Repo(repo)

    def clone(self):
        return ClonedTarget(self.jail, self.ports, self.repo)

    def build(self, packages):
        poudriere.bulk(self.jail.name, self.ports.name, packages)

class ClonedTarget(Target):
    def __init__(self, jail, ports, repo):
        self.jail = jail.clone()
        self.ports = ports.clone()
        self.repo_mnt = (
            poudriere.PACKAGES_BASE /
            '{}-{}'.format(self.jail.name, self.ports.name)
        )
        self.repo = repo.clone(self.repo_mnt)

    def __del__(self):
        if hasattr(self, 'repo'):
            del self.repo

        if hasattr(self, 'repo_mnt'):
            self.repo_mnt.rmdir()
