from pathlib import Path
from pkg_resources import resource_string
from shlex import quote as shquote
from shutil import rmtree
from string import Template

from ..common import to_thread
from .util import zfs,process
from .jail import Jail
from .ports import Ports
from .build import Build

class Poudriere:
    def __init__(self, etc_path):
        self.path_conf    = etc_path / 'poudriere.conf'
        self.path_d       = etc_path / 'poudriere.d'
        self.path_jails_d = self.path_d / 'jails'
        self.path_ports_d = self.path_d / 'ports'
        self.cmd = ('/usr/local/bin/poudriere', '-e', str(etc_path))

    def __call__(self, *args):
        return process(*self.cmd + args)

    def api(self):
        return self('api')

    async def _prop_get(self, func, name, prop):
        return await (await (self.api() << f"{func} {name} {prop}"))

    async def _prop_set(self, func, name, **props):
        await (
            await (
                self.api() << (
                    f"{func} {shquote(name)} {shquote(prop)} {shquote(value)}"
                    for prop,value in props.items()
                )
            )
        )

    async def jget(self, name, prop):
        return await self._prop_get('jget', name, prop)

    async def jset(self, name, **props):
        await self._prop_set('jset', name, **props)

    async def pget(self, name, prop):
        return await self._prop_get('pget', name, prop)

    async def pset(self, name, **props):
        await self._prop_set('pset', name, **props)

    @to_thread
    def rename_jail_conf(self, name, newname):
        (self.path_jails_d / name).rename(self.path_jails_d / newname)

    async def remember_ports(self, name, mnt, timestamp):
        await self.pset(name, mnt=mnt, method='null', timestamp=timestamp)

    @to_thread
    def forget_ports(self, name):
        rmtree(self.path_ports_d / name)

    def write_conf(self, dset):
        tmpl = Template(
            resource_string(__name__, 'poudriere.conf').decode()
        )
        zpool,sep,zrootfs = dset.name.partition('/')
        self.path_conf.write_text(
            tmpl.substitute(
                ZPOOL   = zpool,
                ZROOTFS = f"{sep}{zrootfs}",
                BASEFS  = dset.mountpoint,
            )
        )

class Environment:
    PROPERTY = "poudomatic:environment"
    VERSION = 1

    DATASETS = (
        ( '.m',        None            ),
        ( 'cache',     None            ),
        ( 'ccache',    zfs.COMPRESSION ),
        ( 'distfiles', None            ),
        ( 'etc',       zfs.COMPRESSION ),
        ( 'jails',     None            ),
        ( 'logs',      None            ),
        ( 'ports',     zfs.COMPRESSION ),
        ( 'packages',  None            ),
        ( 'wrkdirs',   None            ),
    )

    @classmethod
    async def new(cls, dataset, runtime):
        self = cls()
        self.runtime = runtime

        if (dset := await zfs.get_dataset(dataset)) is None:
            raise Exception(f"ZFS dataset '{dataset}' doesn't exist.")

        if not zfs.is_filesystem(dset):
            raise Exception(f"ZFS dataset '{dataset}' is no filesystem.")

        if dset.mountpoint is None:
            raise Exception(f"ZFS dataset '{dataset}' is not mounted.")

        self.dset = dset
        self.path = Path(dset.mountpoint)
        self.etc_path = self.path / 'etc'
        self.poudriere = Poudriere(self.etc_path)

        if (version := zfs.get_property(dset, cls.PROPERTY)) is None:
            await self.setup()
        else:
            await self.upgrade(int(version))

        self.dset_jails = await zfs.get_dataset(f"{dataset}/jails")
        self.dset_ports = await zfs.get_dataset(f"{dataset}/ports")

        return self

    @to_thread
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

        # disable compression on root dataset
        zfs.set_properties(self.dset, zfs.NOCOMPRESSION)

        # create child datasets
        for name,props in self.DATASETS:
            zfs.create_dataset(f"{self.dset.name}/{name}", props)

        # write configuration file for poudriere
        self.poudriere.write_conf(self.dset)

        # set properties
        zfs.set_properties(self.dset, {
            self.PROPERTY:    self.VERSION,
            "poudriere:type": "data",
        })

    @to_thread
    def upgrade(self, old_version):
        if old_version == self.VERSION:
            return

        self.poudriere.write_conf(self.dset)

        for ver in range(old_version + 1, self.VERSION + 1):
            getattr(self, f"upgrade_to_{ver}")()

    async def create_jail(self, version):
        return await Jail.create(self, version)

    async def create_ports(self, branch):
        return await Ports.create(self, branch)

    async def get_jail(self, version):
        return await Jail.get(self, version)

    async def get_ports(self, branch):
        return await Ports.get(self, branch)

    async def build(self, jail_version, ports_branch, target):
        await Build(self, jail_version, ports_branch, target)
