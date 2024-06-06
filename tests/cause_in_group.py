def f1():
    f2()


def f2():
    try:
        g1()
    except Exception as e:
        a = e
    else:
        assert False
    raise ExceptionGroup("Hi", [a])


def g1():
    g2()


def g2():
    try:
        h1()
    except Exception as e:
        raise Exception from e


def h1():
    h2()


def h2():
    raise Exception


f1()
