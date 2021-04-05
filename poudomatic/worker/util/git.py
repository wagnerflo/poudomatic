from git import Repo
from ...common import to_thread

clone_from = to_thread(Repo.clone_from)
