from asyncio import get_running_loop
from contextlib import asynccontextmanager
from functools import partial,wraps
from os import mkdir
from os.path import abspath
from pathlib import Path
from shutil import copytree,rmtree
from tempfile import mkdtemp

def to_thread(func):
    @wraps(func)
    def wrapper(*args, **kws):
        try:
            loop = get_running_loop()
        except RuntimeError:
            loop = None
        if loop:
            return loop.run_in_executor(
                None, partial(func, *args, **kws)
            )
        else:
            return func(*args, **kws)
    return wrapper

abspath = to_thread(abspath)
copytree = to_thread(copytree)
mkdir = to_thread(mkdir)
mkdtemp = to_thread(mkdtemp)
rmtree = to_thread(rmtree)

@asynccontextmanager
async def temp_copy(src, dir=None, ignore_errors=False):
    if not (src := Path(src)).is_dir():
        raise Exception()
    dst = Path(await mkdtemp(dir=dir))
    await copytree(src, dst, dirs_exist_ok=True, symlinks=True)
    try:
        yield dst
    finally:
        await rmtree(dst, ignore_errors=ignore_errors)

__all__ = (
    "to_thread",
    "abspath",
    "copytree",
    "mkdir",
    "mkdtemp",
    "rmtree",
    "temp_copy",
)
