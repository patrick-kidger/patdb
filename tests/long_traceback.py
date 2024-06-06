def f(i):
    if i == 0:
        raise ValueError("Kaboom!")
    else:
        f(i - 1)


f(50)
