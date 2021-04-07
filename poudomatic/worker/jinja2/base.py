from jinja2 import nodes

def load_from_context(head, *postfix):
    head = nodes.Name(head, "load")
    for part in postfix:
        head = nodes.Getattr(head, part, "load")
    return head

def parse_strings(parser):
    stream = parser.stream
    token = stream.expect("string")
    buf = [token.value]
    lineno = token.lineno
    while stream.current.type == "string":
        buf.append(stream.current.value)
        next(stream)
    return nodes.Const("".join(buf), lineno=lineno)

class DispatchParseMixin:
    def dispatch(self, funcname, *args, **kwds):
        return getattr(self, funcname)(*args, **kwds)

    def parse(self, parser):
        stream = parser.stream
        token = next(stream)
        return self.dispatch(
            f"parse_{token.value}", parser, stream, token, token.lineno
        )
