from collections import defaultdict
from contextlib import contextmanager
from logging import getLogger
from multiprocessing.pool import ThreadPool
from pathlib import Path
from pydantic import BaseModel, Field
from shutil import copyfile
from typing import Literal, Optional, Union

from . import files
from .srctree import SourceTree
from .util import zfs,git,process
from .versions import *


class Model(BaseModel):
    @classmethod
    def _get_value(cls, field, **kwargs):
        if isinstance(field, FreeBSDBranch):
            return field.short
        elif isinstance(field, FreeBSDVersion):
            return field.shortname
        elif isinstance(field, PortsBranchVersion):
            return field.name
        return super()._get_value(field, **kwargs)


class CreateJailTask(Model):
    version: FreeBSDVersion

    def run(self, env, task_id):
        log = getLogger("create_jail")

        # see if we can find a jail of exactly that version
        if (jail := env.get_jail(self.version)) is not None:
            return jail

        # let's build one
        with ( zfs.temp_dataset(env.dset_src, mountpoint="/usr/obj"),
               zfs.temp_dataset(env.dset_jails) as jail_dset,
               SourceTree.activate(env, self.version) as src_dset,
               env.get_poudriere(task_id) as poudriere ):
            prefix,_,name = jail_dset.name.rpartition("/")

            # build jail from source
            poudriere(
                "jail", "-c", "-b", "-j", name, "-f", "none",
                "-m", f"src={src_dset.mountpoint}",
            ) >> log.info

            # rename dataset
            zfs.rename_dataset(
                jail_dset, f"{prefix}/{self.version.shortname}"
            )

        return env.get_jail(self.version)


class UpdatePortsTask(Model):
    branch: PortsBranchVersion

    def run(self, env, task_id):
        log = getLogger("update_ports")

        if (ports := env.get_ports(self.branch)) is not None:
            snap = ports.snap
            dset = snap.parent

            with git.open(dset.mountpoint) as repo:
                head_before = repo.head.commit
                repo.remotes.origin.pull()
                head_after = repo.head.commit
                timestamp = head_after.committed_date

                if head_before != head_after:
                    snap = zfs.create_snapshot(dset, timestamp)

        else:
            uri = env.get_config("portstree", "uri")
            branchformat = env.get_config("portstree", "branchformat")
            branchname = branchformat.format(branch=self.branch)

            with zfs.temp_dataset(env.dset_ports) as dset:
                prefix,_,_ = dset.name.rpartition("/")

                with git.clone_from(uri, dset.mountpoint,
                                    branch=branchname,
                                    single_branch=True) as repo:
                    timestamp = repo.head.commit.committed_date

                zfs.create_snapshot(dset, timestamp)
                zfs.rename_dataset(dset, f"{prefix}/{self.version.name}")

        return env.get_ports(self.branch)


@contextmanager
def prepare_build(env, task_id, log, jail_version, ports_branch, targets):
    jail = env.get_jail(jail_version)
    ports = env.get_ports(ports_branch)
    makeconf = env.etc_path / f"{jail.name}-{ports.name}-make.conf"

    with ( env.get_poudriere(task_id) as pourdiere,
           ports.clone() as ports_dset ):

        portsdir = Path(ports_dset.mountpoint)
        generated = []

        # copy make conf
        if makeconf.exists():
            copyfile(makeconf, pourdiere.path_make_conf)

        # register portstree and jail with pourdiere
        pourdiere.register_ports(ports, portsdir)
        pourdiere.register_jail(jail)

        # run portja
        if targets:
            process(
                "portja",
                portsdir, pourdiere.path_make_conf, *targets
            ) >> log.info

            # find which ports were generated
            try:
                generated = (portsdir / "portja.generated").read_text().split()
            except FileNotFoundError:
                pass

        yield (generated, pourdiere, jail, ports)

class RunBuildTask(Model):
    jail_version: FreeBSDVersion
    ports_branch: PortsBranchVersion
    portja_targets: list[str]
    origins: list[str]

    def run(self, env, task_id):
        log = getLogger("run_build")

        jail_version = self.jail_version
        ports_branch = self.ports_branch
        targets = self.portja_targets
        origins = self.origins
        packages = env.get_packages(jail_version, ports_branch)

        with ( prepare_build(env, task_id, log, jail_version, ports_branch, targets)
                 as (generated, pourdiere, jail, portstree),
               packages.transaction() ):

            if not origins:
                origins = generated

            # only continue if we have ports to build
            if not origins:
                log.info("No ports to build.")
                return

            with ThreadPool(1) as pool:
                # start pourdiere in thread
                result = pool.apply_async(
                    pourdiere.bulk,
                    ("-j", jail.name, "-p", portstree.name, "-N", *origins),
                    dict(logger=log)
                )

                # TODO: watch files in main thread
                # ...

                errors = result.get()

            pourdiere.clean_logs()
            stats = pourdiere.read_bulk_stats()

            # only continue if packages were built
            if not stats.built:
                return

            pkglist = " ".join(stats.built)
            log.info(f"Packages built: {pkglist}")

            # start jail, mount repository into it, run update script
            with ( pourdiere.jail(jail.name, portstree.name) as pj,
                   mount_nullfs(packages.mountpoint, pj.path / "pkg") ):
                script = files.read_template(
                    "repo_update.sh",
                    pkg_printf_c=files.read("pkg_printf.c"),
                    pkg_latest_c=files.read("pkg_latest.c"),
                    packages=pkglist,
                )
                pj.exec("/bin/sh", "-s") << script >> log.info

@contextmanager
def mount_nullfs(src, tgt):
    Path(tgt).mkdir(exist_ok=True)
    process("mount", "-t", "nullfs", src, tgt).run()
    try:
        yield
    finally:
        process("umount", tgt).run()

class GetDependsTask(Model):
    jail_version: FreeBSDVersion
    ports_branch: PortsBranchVersion
    origin: str
    portja_target: Optional[str] = None

    def run(self, env, task_id):
        log = getLogger("get_depends")

        jail_version = self.jail_version
        ports_branch = self.ports_branch
        targets = [] if self.portja_target is None else [self.portja_target]

        with prepare_build(env, task_id, log, jail_version, ports_branch, targets) \
               as (generated, pourdiere, jail, portstree):
            errors = pourdiere.bulk(
                "-j", jail.name, "-p", portstree.name, "-n", self.origin,
                logger=log
            )
            if errors:
                pourdiere.clean_logs(with_task=True)
                raise Exception("; ".join(errors))

        stats = pourdiere.read_bulk_stats()
        pourdiere.clean_logs(with_task=True)
        return stats.depends


__all__ = (
    "CreateJailTask",
    "UpdatePortsTask",
    "RunBuildTask",
    "GetDependsTask",
)
