import copy
import dataclasses
import re

from yamap import *
from . import model
from .target import Target
from .templates.base import Template

@dataclasses.dataclass
class Context:
    cwd:       str  = None
    snippets:  dict = dataclasses.field(default_factory=dict)
    defaults:  dict = dataclasses.field(default_factory=dict)
    templates: dict = dataclasses.field(default_factory=dict)
    targets:   list = dataclasses.field(default_factory=list)

    def copy(self):
        return dataclasses.replace(self, **{
            f.name: copy.copy(getattr(self, f.name))
            for f in dataclasses.fields(self)
        })

    def update(self, data):
        for f in dataclasses.fields(self):
            if f.type is dict:
                getattr(self, f.name).update(data.pop(f.name, {}))
            elif f.type is list:
                getattr(self, f.name).extend(data.pop(f.name, []))

re_package = r'(?i)([a-z][a-z0-9-]*/[a-z][a-z0-9._-]*)'
re_name = r'(?i)([a-z][a-z0-9_-]*)'
re_dependency = re_package + r'((?:(?:=|[<>]=?)[^<>=]+){0,2})'

schema_resolvable = yaoneof(
  yastr,
  yastr(
    tag = '!#/.+',
    construct = lambda constructor,node: model.Script(
      node.tag[2:],
      constructor.construct_scalar(node)
    ),
  ),
  yastr(
    tag = '!apply',
    type = model.SnippetReference
  ),
)

schema_common = (
  yamap()
    .zero_or_one(
      'snippets',
      yamap().zero_or_more(re_name, schema_resolvable)
    )
    .zero_or_one(
      'defaults',
      yamap().zero_or_more(re_name, schema_resolvable)
    )
)

schema_config = (
  schema_common
    .zero_or_one(
      'templates',
      yamap().zero_or_more(
        re_name,
        yastr(type=Template.import_from_name)
      )
    )
    .zero_or_one(
      'targets',
      yaseq().case(
        yamap(type=Target, unpack=True)
          .exactly_one('jail', yastr)
          .exactly_one('ports', yastr)
          .exactly_one('repo', yastr)
      )
    )
)

def load_config(*docs):
    context = Context()
    for doc in docs:
        context.update(schema_config.load(doc))
    return context

def load_poudomatic(directory, context):
    stream = (directory / '.poudomatic.yaml').read_text()
    context = context.copy()
    context.cwd = directory

    def Dependency(key, value=None):
        res = re.fullmatch(re_dependency, key)
        return (
            res.group(1),
            model.Dependency(key, value, config_context=context)
        )

    def Package(key, value):
        return (
            key,
            model.Package(key, value, config_context=context)
        )

    poudomatic_dependency = (
      yamap()
        .exactly_one('src', yastr)
    )

    dependency_list = yaoneof(
      yaseq(type=dict)
        .case(
          yastr(type=Dependency, value=re_dependency)
        )
        .case(
          yamap(type=Dependency, squash=True, unpack=True)
            .exactly_one(re_package, poudomatic_dependency)
        ),
      yamap()
        .one_or_more(
          re_dependency,
          type = Dependency,
          schema = yaoneof(yanull, poudomatic_dependency)
        )
    )

    schema_templates = yaentry(required=True)
    for key,cls in context.templates.items():
        schema_templates = schema_templates.case(key, cls.config_schema, cls)
    schema_templates = yamap(type=None, squash=True).entry(schema_templates)

    schema_poudomatic = (
      schema_common
        .zero_or_more(
          re_package,
          type = Package,
          schema = (
            yamap()
              .zero_or_one('version', schema_resolvable)
              .zero_or_one('RUN_DEPENDS', dependency_list)
              .exactly_one('TEMPLATE', schema_templates)
          )
        )
    )

    data = schema_poudomatic.load(stream)
    context.update(data)
    return data
