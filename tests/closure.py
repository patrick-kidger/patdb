def f():
    breakpoint()

    def g():
        x = 5
        del x

    g()


f()
