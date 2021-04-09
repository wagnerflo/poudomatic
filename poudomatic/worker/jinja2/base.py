from jinja2 import nodes

def load_from_context(head, *postfix):
    head = nodes.Name(head, "load")
    for part in postfix:
        head = nodes.Getattr(head, part, "load")
    return head

def parse_token_as_const(parser):
    token = next(parser.stream)
    return nodes.Const(token.value, lineno=token.lineno)

def parse_name_as_const(parser):
    token = parser.stream.expect("name")
    return nodes.Const(token.value, lineno=token.lineno)

def parse_keyword_pair(parser):
    key = parse_name_as_const(parser)
    parser.stream.expect("assign")
    return nodes.Pair(key, parser.parse_expression(), lineno=key.lineno)

def parse_keywords(parser):
    items = []
    stream = parser.stream
    lineno = stream.expect("lbrace").lineno
    while stream.current.type != "rbrace":
        if items:
            stream.expect("comma")
        if stream.current.type == "rbrace":
            break
        items.append(parse_keyword_pair(parser))
    next(stream)
    return nodes.Dict(items, lineno=lineno)

class DispatchParseMixin:
    def dispatch(self, funcname, *args, **kwds):
        return getattr(self, funcname)(*args, **kwds)

    def parse(self, parser):
        stream = parser.stream
        token = next(stream)
        return self.dispatch(
            f"parse_{token.value}", parser, stream, token, token.lineno
        )
