from importlib import resources
from pathlib import Path
from string import Template

class SilcrowTemplate(Template):
    delimiter = "§"

def read(filename):
    return resources.read_text(__package__, filename)

def read_template(filename, **kwargs):
    return SilcrowTemplate(read(filename)).safe_substitute(kwargs)

def template_to_file(filename, dest, **kwargs):
    Path(dest).write_text(read_template(filename, **kwargs))
