from contextlib import contextmanager
from git import Repo

@contextmanager
def clone_from(*args, **kwds):
    repo = Repo.clone_from(*args, **kwds)
    try:
        yield repo
    finally:
        repo.close()

@contextmanager
def open(*args, **kwds):
    repo = Repo(*args, **kwds)
    try:
        yield repo
    finally:
        repo.close()

def count_head(repo):
    return repo.head.commit.count()

def sha_head(repo):
    return repo.head.commit.hexsha
