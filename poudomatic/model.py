from dataclasses import dataclass,field
from itertools import chain
from subprocess import check_output
from weakref import WeakKeyDictionary

from .templates.base import Template

registry = WeakKeyDictionary()

@dataclass(frozen=True)
class ResolvingNamespaceProperty:
    use_defaults: bool = False
    plain: bool = False
    key: str = None
    default: str = None

    def __set_name__(self, owner, name):
        if self.key is None:
            object.__setattr__(self, 'key', name)

    def __get__(self, obj, objtype=None):
        if obj not in registry:
            raise Exception('Unknown {}'.format(obj))

        dct,config_context = registry[obj]

        try:
            val = dct[self.key]
        except KeyError:
            if not self.use_defaults:
                return self.default
            val = config_context.defaults.get(self.key)

        if self.plain:
            return val

        while isinstance(val, SnippetReference):
            val = config_context.snippets[val.key]

        if isinstance(val, Script):
            val = val.run(str(config_context.cwd))

        return val

class ResolvingNamespace:
    def __init__(self, dct, config_context):
        registry[self] = (dct, config_context)

class Script:
    def __init__(self, arg0, code):
        self._arg0 = arg0
        self._code = code

    def run(self, cwd):
        return check_output(
            self._arg0,
            input = self._code,
            text = True,
            cwd = cwd,
        )

    def __repr__(self):
        return '!#{} ...'.format(self._arg0)

class SnippetReference:
    def __init__(self, key):
        self.key = key

    def __repr__(self):
        return "!apply '{}'".format(self.key)


class Dependency(ResolvingNamespace):
    src: str = ResolvingNamespaceProperty()

    def __init__(self, name, dct=None, config_context=None):
        super().__init__({} if dct is None else dct, config_context)
        self.name = name
        self.is_external = dct is None

    def __repr__(self):
        return '<Dependecy: {}>'.format(self.name)

class Package(ResolvingNamespace):
    version: str = ResolvingNamespaceProperty(use_defaults=True)
    RUN_DEPENDS: str = ResolvingNamespaceProperty(plain=True, default={})
    TEMPLATE: Template = ResolvingNamespaceProperty(plain=True)

    def __init__(self, name, dct, config_context):
        super().__init__(dct, config_context)
        self.name = name

    @property
    def dependencies(self):
        return chain(
            self.RUN_DEPENDS.values(),
        )

    def generate_port(self, base, distfile):
        portdir = base / self.name

        if portdir.exists():
            raise Exception(
                'Port {} already in Ports directory'.format(self.name)
            )

        portdir.mkdir(parents=True)
        self.TEMPLATE.generate(self, portdir, distfile)
