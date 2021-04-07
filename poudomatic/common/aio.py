from asyncio import get_running_loop
from contextlib import (
    asynccontextmanager,
    AsyncExitStack,
    contextmanager,
)
from contextvars import ContextVar
from functools import partial,wraps
from inspect import isgeneratorfunction
from sys import modules,_getframe

_gen_stop = object()

async def _unblocked_generator(loop, gen):
    gen = await loop.run_in_executor(None, gen)
    def next():
        try:
            return gen.__next__()
        except StopIteration:
            return _gen_stop
    while (item := await loop.run_in_executor(None, next)) is not _gen_stop:
        yield item

def unblocked(func, *args, **kwds):
    topname = func.__name__
    calling = True

    if getattr(modules[func.__module__], topname, None) is not func:
        at_frame = _getframe(1)
        calling = (
            at_frame.f_locals.get(topname) is func or
            at_frame.f_globals.get(topname) is func
        )

    @wraps(func)
    def wrapper(*args, **kwds):
        try:
            loop = get_running_loop()
        except RuntimeError:
            loop = None

        if not loop:
            return func(*args, **kwds)

        elif isgeneratorfunction(func):
            return _unblocked_generator(loop, partial(func, *args, **kwds))

        else:
            return loop.run_in_executor(None, partial(func, *args, **kwds))

    if calling:
        return wrapper(*args, **kwds)

    return wrapper

class _UnblockedContextManager:
    __slots__ = ("step", "loop")

    def __init__(self, cm, args, kwds):
        self.step = partial(self._setup, cm, args, kwds)
        self.loop = get_running_loop()

    def _setup(self, cm, args, kwds):
        cm = cm(*args, **kwds)
        self.step = cm.__exit__
        return cm.__enter__()

    def __aenter__(self):
        return self.loop.run_in_executor(None, self.step)

    def __aexit__(self, *args):
        return self.loop.run_in_executor(None, self.step, *args)

def unblockedcontextmanager(cm):
    if isgeneratorfunction(cm):
        cm = contextmanager(cm)
    @wraps(cm)
    def wrapper(*args, **kwds):
        return _UnblockedContextManager(cm, args, kwds)
    return wrapper

_cleanup_stack = ContextVar("_cleanup_stack")

async def _add_cleanup(item):
    if hasattr(item, "__aenter__") and hasattr(item, "__aexit__"):
        return await _cleanup_stack.get().enter_async_context(item)
    else:
        _cleanup_stack.get().push_async_exit(_run_coro(item))

def _run_coro(coro):
    @wraps(coro)
    async def wrapper(*args, **kwds):
        return await coro
    return wrapper

def cleanup(func):
    @wraps(func)
    async def wrapper(*args, **kwds):
        async with AsyncExitStack() as stack:
            _cleanup_stack.set(stack)
            return await func(*args, **kwds)
    return wrapper

def ainit(func):
    @wraps(func)
    @classmethod
    @asynccontextmanager
    async def wrapper(cls, *args, **kwds):
        async with AsyncExitStack() as stack:
            _cleanup_stack.set(stack)
            self = cls()
            await func(self, *args, **kwds)
            yield self
    return wrapper

cleanup.push = _add_cleanup
ainit.push_del = _add_cleanup

__all__ = (
    "ainit",
    "cleanup",
    "unblocked",
    "unblockedcontextmanager",
)
