from libzfs import (
    ZFS,
    ZFSDataset,ZFSSnapshot,
    ZFSException,
    Error as ZFSErrorCode
)
from tempfile import _RandomNameSequence

_zfs = ZFS()

for name in ('get_object', 'get_dataset', 'get_dataset_by_path'):
    locals()[name] = getattr(_zfs, name)

def create_snapshot(dataset, name):
    fullname = '{}@{}'.format(dataset.name, name)
    dataset.snapshot(fullname)
    return get_object(fullname)

def create_clone(snapshot, name, **opts):
    if isinstance(snapshot, TemporarySnapshot):
        snapshot = snapshot.snap
    snapshot.clone(name, opts)
    return get_object(name)

class TemporarySnapshot:
    def __init__(self, dataset, name):
        self.snap = create_snapshot(dataset, name)

    def __del__(self):
        if hasattr(self, 'snap'):
            self.snap.delete(recursive_children=True)

class TemporaryClone:
    def __init__(self, obj, name, **opts):
        if isinstance(obj, ZFSDataset):
            for snapname in _RandomNameSequence():
                try:
                    self.snap = TemporarySnapshot(obj, snapname)

                except ZFSException as exc:
                    if exc.code == ZFSErrorCode.EXISTS:
                        continue

                else:
                    break
        else:
            self.snap = obj

        self.fs = create_clone(self.snap, name, **opts)

    def __del__(self):
        if hasattr(self, 'fs'):
            for dep in self.fs.dependents:
                if isinstance(dep, ZFSDataset) and dep.mountpoint:
                    dep.umount(True)
                dep.delete()
            self.fs.umount(True)
            self.fs.delete()

    def mount(self):
        self.fs.mount()
