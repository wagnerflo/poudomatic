from argparse import ArgumentParser,FileType
from fasteners import InterProcessLock
from pathlib import Path
from pkgdiff import compare as pkg_compare
from pkg_resources import resource_stream
from threading import Thread

from .config import load_config
from .pkg import index_pkg_paths,PkgParts
from .repository import Repository

def try_open(path):
    try:
        return (open(path, 'rb'),)
    except (FileNotFoundError, PermissionError):
        return ()

if True:
    parser = ArgumentParser()
    parser.add_argument(
        '-c', '--config', action='append',
        default=[
            resource_stream(__name__, 'defaults.conf'),
            *try_open('/usr/local/etc/poudomatic.conf'),
        ],
        type=FileType('rb')
    )
    parser.add_argument(
        'repository',
    )
    parser.add_argument(
        'packages', nargs='*',
    )

    args = parser.parse_args()
    config_context = load_config(*(
        p.read().decode('utf-8') for p in args.config
    ))
    repo = Repository.clone_from_url(args.repository, config_context)
    repos = { repo.url: repo }

    if args.packages:
        packages = {
            pkg: (repo[pkg], repo) for pkg in args.packages if pkg in repo
        }
    else:
        packages = {
            name: (pkg, repo) for name,pkg in repo.packages.items()
        }

    to_resolve = []
    to_resolve.extend(pkg for pkg,repo in packages.values())

    while to_resolve:
        current_pkg = to_resolve.pop()

        # find dependencies in packages we haven't looked add
        for dep in current_pkg.dependencies:

            # not managed by poudomatic or already known?
            if dep.is_external or dep.name in packages:
                continue

            # get the specified repository
            if dep.src not in repos:
                repos[dep.src] = Repository.clone_from_url(
                    dep.src, config_context
                )

            repo = repos[dep.src]
            dep_pkg = repo[dep.name]
            to_resolve.append(dep_pkg)
            packages[dep_pkg.name] = (dep_pkg, repo)

    for target in config_context.targets:
        clone = target.clone()

        # generate ports
        for pkg,repo in packages.values():
            pkg.generate_port(clone.ports.mnt, repo.generate_distfile())

        # run build
        clone.build(packages.keys())

        # compare repositories
        with InterProcessLock(target.repo.lockfile):
            reindex = False
            current = index_pkg_paths(target.repo.all_packages)

            for pkgfile in clone.repo.all_packages:
                pkg = PkgParts(pkgfile.stem)

                # do we know one or more packages with the same name?
                if pkg.name in current:
                    pkg_current = current[pkg.name]
                    # compare against same version
                    if pkg.fullversion in pkg_current:
                        to_compare = pkg_current[pkg.fullversion]
                    # or latest version
                    else:
                        to_compare = next(iter(pkg_current.values()))

                    equal = pkg_compare(
                        str(to_compare), str(pkgfile), exclude=(
                            'version',
                        )
                    )
                    if equal:
                        print(pkgfile, '==', to_compare)
                        continue

                reindex = True
                target.repo.add_package(pkgfile)

            if reindex:
                target.repo.refresh_catalogue()
