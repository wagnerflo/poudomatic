from contextlib import asynccontextmanager
from libzfs import (
    DatasetType as ZFSDatasetType,
    Error as ZFSErrorCode,
    ZFS,
    ZFSUserProperty,
    ZFSException,
)
from random import choices
from .util import to_thread

def _tempnames():
    while True:
        yield "".join(
            choices("abcdefghijklmnopqrstuvwxyz0123456789_", k=8)
        )

_zfs = ZFS()
get_pool = to_thread(_zfs.get)
get_dataset = to_thread(_zfs.get_dataset)
get_snapshot = to_thread(_zfs.get_snapshot)
create_dataset = to_thread(_zfs.create)

@to_thread
def create_snapshot(dset, name):
    name = f"{dset.name}@{name}"
    dset.snapshot(name)
    return _zfs.get_snapshot(name)

@to_thread
def get_dataset(name):
    try:
        return _zfs.get_dataset(name)
    except ZFSException as exc:
        if exc.code != ZFSErrorCode.NOENT:
            raise

@to_thread
def set_properties(dataset, props):
    for key,value in props.items():
        dataset.properties[key] = ZFSUserProperty(str(value))

def is_filesystem(dataset):
    return dataset.type == ZFSDatasetType.FILESYSTEM

@to_thread
def create_dataset(name, fsprops={}, mount=True):
    pool,_,_ = name.partition('/')
    pool = _zfs.get(pool)
    pool.create(name, fsprops)
    dset = _zfs.get_dataset(name)
    if mount:
        dset.mount()
    return dset

@to_thread
def find_dataset(root, fsprops={}):
    for child in root.children_recursive:
        print(child)

@to_thread
def destroy_dataset(name):
    dset = _zfs.get_dataset(name)
    for dep in dset.dependents:
        if is_filesystem(dep) and dep.mountpoint:
            dep.umount(True)
        dep.delete()
    dset.umount(True)
    dset.delete()

@to_thread
def rename_dataset(dset, newname):
    dset.rename(newname)
    return _zfs.get_dataset(newname)

@to_thread
def sorted_snapshots(dset, key=None, reverse=False):
    if key is None:
        key = lambda s: s.snapshot_name
    return sorted(dset.snapshots, key=key, reverse=reverse)

@to_thread
def create_clone(snap, name, fsprops={}, mount=True):
    snap.clone(name, fsprops)
    dset = _zfs.get_dataset(name)
    if mount:
        dset.mount()
    return dset

@asynccontextmanager
async def temp_dataset(root, fsprops={}, mount=True):
    for name in _tempnames():
        try:
            name = f"{root.name}/{name}"
            dset = await create_dataset(name, fsprops=fsprops, mount=mount)
            break
        except ZFSException as exc:
            if exc.code == ZFSErrorCode.EXISTS:
                continue
    try:
        yield dset
    finally:
        try:
            await destroy_dataset(name)
        except ZFSException as exc:
            if exc.code != ZFSErrorCode.NOENT:
                raise

@asynccontextmanager
async def temp_clone(snap, fsprops={}, mount=True):
    prefix = snap.parent.name
    for name in _tempnames():
        try:
            name = f"{prefix}/{name}"
            dset = await create_clone(snap, name, fsprops=fsprops, mount=mount)
            break
        except ZFSException as exc:
            if exc.code == ZFSErrorCode.EXISTS:
                continue
    try:
        yield dset
    finally:
        try:
            await destroy_dataset(name)
        except ZFSException as exc:
            if exc.code != ZFSErrorCode.NOENT:
                raise

COMPRESSION   = { 'compression': 'zstd' }
NOCOMPRESSION = { 'compression': 'off'  }
NOATIME       = { 'atime':       'off'  }
