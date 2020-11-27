from hashlib import sha256
from importlib import import_module
from inspect import getmro
from jinja2 import Environment,PackageLoader
from pathlib import Path
from yamap import *

class Template:
    filters = {
        'dirname': lambda value: str(Path(value).parent)
    }

    @classmethod
    def import_from_name(base, name):
        mod_name,cls_name = name.rsplit('.', 1)
        mod = import_module(mod_name)
        if not hasattr(mod, cls_name):
            raise Exception(
                '{} has no member {}'.format(mod, cls_name)
            )
        cls = getattr(mod, cls_name)
        if not issubclass(cls, base):
            raise Exception(
                '{} is not a subclass of {}'.format(cls, base)
            )
        return cls

    def __init__(self, name, config):
        self.name = name
        self.config = config
        self.env = Environment(
            loader = PackageLoader(self.__module__, ''),
        )

        for cls in reversed(getmro(self.__class__)):
            if issubclass(cls, Template) and 'filters' in cls.__dict__:
                self.env.filters.update(cls.filters)

    def render_template(self, path, tmpl, **ctx):
        with path.open('w') as fp:
            self.env.get_template(tmpl).stream(ctx).dump(fp)

        print(path)
        print(path.read_text())

    def generate_distinfo(self, pkg, portdir, distfile):
        array = bytearray(64 * 1024)
        size = 0
        sha = sha256()
        with distfile.open('rb') as fp:
            length = fp.readinto(array)
            size = size + length
            sha.update(array[:length])

        with (portdir / 'distinfo').open('w') as fp:
            fp.write('SHA256 ({name}) = {sha}\nSIZE ({name}) = {size}\n'.format(
                name=distfile.name,
                sha=sha.hexdigest(),
                size=size,
            ))

    def generate_descr(self, pkg, portdir, distfile):
        self.render_template(
            portdir / 'pkg-descr',
            'pkg-plist.tmpl',
            pkg = pkg,
        )

    def generate_makefile(self, pkg, portdir, distfile):
        self.render_template(
            portdir / 'Makefile',
            'Makefile.{}.tmpl'.format(self.__class__.__name__),
            config = self.config,
            pkg = pkg,
            distfile = distfile,
        )

    def generate_plist(self, pkg, portdir, distfile):
        self.render_template(
            portdir / 'pkg-plist',
            'pkg-plist.{}.tmpl'.format(self.__class__.__name__),
            config = self.config,
            pkg = pkg,
        )

    def generate(self, pkg, portdir, distfile):
        self.generate_distinfo(pkg, portdir, distfile)
        self.generate_descr(pkg, portdir, distfile)
        self.generate_makefile(pkg, portdir, distfile)
        self.generate_plist(pkg, portdir, distfile)

__all__ = (
    'Template',
    'yaoneof',
    'yascalar',
    'yastr',
    'yanull',
    'yabool',
    'yanumber',
    'yaint',
    'yafloat',
    'yaentry',
    'yamap',
    'yaseq',
)
