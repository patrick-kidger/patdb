def f(i):
    __tracebackhide__ = True
    if i == 0:
        raise ValueError("Kaboom!")
    else:
        f(i - 1)


f(50)
