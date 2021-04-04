from contextlib import contextmanager
from itertools import chain
from libzfs import (
    DatasetType as ZFSDatasetType,
    Error as ZFSErrorCode,
    ZFS,
    ZFSUserProperty,
    ZFSException,
)
from pathlib import Path
from random import choices

_unset = object()
_zfs = ZFS()
_tempnames = (
    "".join(choices("abcdefghijklmnopqrstuvwxyz0123456789_", k=8))
    for _ in iter(int, 1)
)

def _prepare_fsprops(fsprops, mntpnt):
    fsprops = fsprops or {}
    if mntpnt != _unset:
        fsprops["mountpoint"] = mntpnt or "none"
    return { str(k): str(v) for k,v in fsprops.items() }

def get_dataset(name):
    try:
        return _zfs.get_dataset(name)
    except ZFSException as exc:
        if exc.code != ZFSErrorCode.NOENT:
            raise

def mount_dataset(dset, force=False):
    if dset.mountpoint or get_property(dset, "mountpoint") in ("none", "legacy"):
        return
    if force and get_property(dset, "canmount") != "on":
        set_properties(dset, { "canmount": "noauto" })
    if get_property(dset, "canmount") != "off":
        dset.mount()

def create_dataset(name, fsprops=None,
                   mountpoint=_unset, mount=True, force_mount=False):
    pool,_,_ = name.partition("/")
    pool = _zfs.get(pool)
    pool.create(name, _prepare_fsprops(fsprops, mountpoint))
    dset = _zfs.get_dataset(name)
    if mount:
        mount_dataset(dset, force_mount)
    return dset

def rename_dataset(dset, newname):
    dset.rename(newname)
    return _zfs.get_dataset(newname)

def set_properties(dset, props):
    for key,value in props.items():
        dset.properties[key] = ZFSUserProperty(str(value))

def get_property(dset, prop):
    if (prop := dset.properties.get(prop)) is not None:
        return prop.value

def is_filesystem(dset):
    return dset.type == ZFSDatasetType.FILESYSTEM

def is_snapshot(dset):
    return dset.type == ZFSDatasetType.SNAPSHOT

def get_snapshot(name):
    try:
        return _zfs.get_snapshot(name)
    except ZFSException as exc:
        if exc.code != ZFSErrorCode.NOENT:
            raise

def get_newest_snapshot(name):
    if dset := get_dataset(name):
        try:
            return next(iter(sorted_snapshots(dset, reverse=True)))
        except StopIteration:
            pass

def create_snapshot(dset, name):
    name = f"{dset.name}@{name}"
    dset.snapshot(name)
    return _zfs.get_snapshot(name)

def sorted_snapshots(dset,
                     key=lambda s: int(s.properties["createtxg"].value),
                     reverse=False):
    return sorted(dset.snapshots, key=key, reverse=reverse)

def rollback_snapshot(snap):
    snap.rollback()

def create_clone(snap, name, fsprops=None,
                 mountpoint=_unset, mount=True, force_mount=False):
    fsprops =_prepare_fsprops(fsprops, mountpoint)
    snap.clone(name, fsprops)
    dset = _zfs.get_dataset(name)
    if mount:
        mount_dataset(dset, force_mount)
    return dset

def _destroy_dataset(dset):
    try:
        for dep in dset.dependents:
            if is_filesystem(dep) and dep.mountpoint:
                dep.umount(True)
            dep.delete()
        if is_filesystem(dset) and dset.mountpoint:
            dset.umount(True)
        dset.delete()
    except ZFSException as exc:
        if exc.code != ZFSErrorCode.NOENT:
            raise

def _try_tempname(func):
    for name in _tempnames:
        try:
            return func(name)
        except ZFSException as exc:
            if exc.code != ZFSErrorCode.EXISTS:
                raise

@contextmanager
def temp_dataset(root, fsprops=None, mountpoint=_unset, mount=True):
    dset = _try_tempname(
        lambda name: create_dataset(
            f"{root.name}/{name}",
            fsprops=fsprops,
            mountpoint=mountpoint,
            mount=mount,
            force_mount=mount,
        )
    )
    try:
        yield dset
    finally:
        _destroy_dataset(dset)

@contextmanager
def temp_snapshot(dset):
    snap = _try_tempname(lambda name: create_snapshot(dset, name))
    try:
        yield snap
    finally:
        _destroy_dataset(snap)

@contextmanager
def temp_clone(snap, fsprops=None, mountpoint=_unset, mount=True):
    dset = _try_tempname(
        lambda name: create_clone(
            snap, f"{snap.parent.name}/{name}",
            fsprops=fsprops,
            mountpoint=mountpoint,
            mount=mount,
            force_mount=mount,
        )
    )
    try:
        yield dset
    finally:
        _destroy_dataset(dset)

@contextmanager
def temp_mount(dset, mntpnt):
    try:
        set_properties(dset, { "mountpoint": str(mntpnt) })
        dset.mount()
        yield Path(mntpnt)
    finally:
        set_properties(dset, { "mountpoint": "none" })


class props(dict):
    def __add__(self, other):
        return self.__class__(chain(self.items(), other.items()))

COMPRESSION   = props( compression = "zstd" )
NOCOMPRESSION = props( compression = "off"  )
NOATIME       = props( atime       = "off"  )
