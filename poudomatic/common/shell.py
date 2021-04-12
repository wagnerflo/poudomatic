from shlex import quote

def shquote(*args):
    return " ".join(quote(str(arg)) for arg in args)

__all__ = (
    "shquote",
)
