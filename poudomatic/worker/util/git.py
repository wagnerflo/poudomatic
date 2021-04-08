from contextlib import contextmanager
from git import Repo
from ...common import (
    unblocked,
    unblockedcontextmanager,
)

@unblockedcontextmanager
def clone_from(*args, **kwds):
    repo = Repo.clone_from(*args, **kwds)
    try:
        yield repo
    finally:
        repo.close()

@unblocked
def count_head(repo):
    return repo.head.commit.count()

@unblocked
def sha_head(repo):
    return repo.head.commit.hexsha
