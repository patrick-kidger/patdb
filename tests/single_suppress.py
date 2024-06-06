def f1():
    f2()


def f2():
    f3()


def f3():
    try:
        g1()
    except Exception:
        raise ValueError("Stack 1") from None


def g1():
    g2()


def g2():
    g3()


def g3():
    try:
        h1()
    except Exception as e:
        raise ValueError("Stack 2") from e


def h1():
    h2()


def h2():
    h3()


def h3():
    raise RuntimeError("Stack 3")


f1()
