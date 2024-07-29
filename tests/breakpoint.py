def f():
    x = g()
    y = x + 1
    z = y * 2
    return z


def g():
    breakpoint()
    h(x=3)
    return 5


def h(x: int):
    print("hi" * x)


f()
