def f():
    try:
        g1()
    except Exception as e1:
        try:
            g2()
        except Exception as e2:
            a = e1
            b = e2
    c = KeyError()
    raise ExceptionGroup("Egads.", [a, b]) from c  # pyright: ignore


def g1():
    h()


def g2():
    h()


def h():
    raise RuntimeError("It's all gone explodey.")


f()
