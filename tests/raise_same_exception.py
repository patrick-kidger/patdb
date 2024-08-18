def f():
    raise RuntimeError("Foobar!")


def g():
    try:
        f()
    except RuntimeError as e:
        raise e


g()
