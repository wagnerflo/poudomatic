from asyncio import get_running_loop
from select import (
    kqueue, kevent,
    KQ_FILTER_READ,
    KQ_EV_ADD,
    KQ_EV_DELETE,
    KQ_EV_ENABLE,
    KQ_EV_DISABLE,
    KQ_EV_CLEAR,
)
from os import lseek

kq = kqueue()
kqfd = kq.fileno()
futures = {}

class TruncationError(Exception):
    pass

def handle_event():
    if (kev := kq.control(None, 1, 0)):
        fd = kev[0].ident
        fut = futures[fd]

        if kev[0].data < 0:
            fut.set_exception(TruncationError())

        else:
            futures[fd] = fut.get_loop().create_future()
            fut.set_result(None)

async def follow(fp):
    fd = fp.fileno()
    loop = get_running_loop()
    loop.add_reader(kqfd, handle_event)

    kq.control(
        [ kevent(
            fd,
            KQ_FILTER_READ,
            KQ_EV_ADD | KQ_EV_ENABLE | KQ_EV_CLEAR,
          ) ],
        0, 0
    )

    futures[fd] = loop.create_future()

    try:
        while True:
            await futures[fd]
            yield None
    finally:
        kq.control(
            [ kevent(
                fd,
                KQ_FILTER_READ,
                KQ_EV_DELETE | KQ_EV_DISABLE,
            ) ],
            0, 0
        )
        del futures[fd]

__all__ = (
    "follow",
    "TruncationError",
)
