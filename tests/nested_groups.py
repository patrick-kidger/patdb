def make_callstack(msg: str):
    def f():
        g()

    def g():
        h()

    def h():
        raise RuntimeError(msg)

    f()


def make_exception_group(msg: str, num: int):
    exceptions = []
    for i in range(num):
        try:
            make_callstack(f"Hello from {i}\nHere is another line.")
        except Exception as e:
            exceptions.append(e)
        else:
            assert False
    raise ExceptionGroup(msg + "\nAnd a line here too.", exceptions)


def make_nested_exception_group():
    exceptions = []
    try:
        make_exception_group("Group A", 2)
    except Exception as e:
        exceptions.append(e)
    else:
        assert False
    try:
        make_exception_group("Group A2", 1)
    except Exception as e:
        exceptions[0].exceptions[-1].__context__ = e
    else:
        assert False
    try:
        make_exception_group("Group B", 4)
    except Exception as e:
        exceptions.append(e)
    else:
        assert False
    raise ExceptionGroup("Top group\nWith a new line.", exceptions)


make_nested_exception_group()
