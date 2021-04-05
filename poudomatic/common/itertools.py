from random import choices

def head(iterable, default=None):
    try:
        return next(iter(iterable))
    except StopIteration:
        return default

# See https://stackoverflow.com/a/5739258. Iterator that never stops and
# always returns 0.
endless = iter(int, 1)

# Return random 8 character long strings of a base alphabet.
tempnames = (
    "".join(choices("abcdefghijklmnopqrstuvwxyz0123456789_", k=8))
    for _ in endless

)
