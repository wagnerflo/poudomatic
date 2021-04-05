from asyncio import get_running_loop
from functools import partial,wraps

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
