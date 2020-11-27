from pathlib import Path
from subprocess import check_output,Popen,PIPE,STDOUT
from . import zfs

def process_printlines(proc):
    while proc.poll() is None:
        print(proc.stdout.readline(), end='')

def bulk(jail, ports, packages):
    proc = None
    try:
        proc = Popen(
            ('poudriere', 'bulk', '-j', jail, '-p', ports) + tuple(packages),
            stdout=PIPE, stderr=STDOUT,
            text=True,
        )
        process_printlines(proc)
    except KeyboardInterrupt:
        if proc is not None:
            process_printlines(proc)
        raise

def api(*command):
    return check_output(
        ('poudriere', 'api'),
        text=True,
        input=' '.join(command),
    ).strip()

def echo(*rest):
    return api('echo', *rest)

POUDRIERED = Path(echo('${POUDRIERED}'))
JAILSD = POUDRIERED / 'jails'
PORTSD = POUDRIERED / 'ports'

BASEFS = Path(echo('${BASEFS}'))
PORTS_BASE = BASEFS / 'ports'
JAILS_BASE = BASEFS / 'jails'
DATA_BASE = BASEFS / 'data'
PACKAGES_BASE = DATA_BASE / 'packages'

PORTS_FS = zfs.get_dataset(echo('${ZPOOL}${ZROOTFS}/ports'))

DISTFILES = Path(echo('${DISTFILES_CACHE}'))

def jailclean(jail):
    return zfs.get_object('{}@clean'.format(api('jget', jail, 'fs')))

def jailmnt(jail):
    return Path(api('jget', jail, 'mnt'))

def portsmnt(ports):
    return Path(api('pget', ports, 'mnt'))

def portsfs(ports):
    return zfs.get_dataset_by_path(str(portsmnt(ports)))

def clone_jail(src, dst, **kwargs):
    for var in ('arch', 'fs', 'method', 'mnt', 'timestamp', 'version'):
        api('jset', dst, var, kwargs.get(var, '$(jget {} {})'.format(src, var)))

def clone_ports(src, dst, **kwargs):
    for var in ('method', 'mnt', 'timestamp'):
        api('pset', dst, var, kwargs.get(var, '$(pget {} {})'.format(src, var)))
