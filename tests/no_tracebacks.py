e1 = KeyError()
e2 = RuntimeError()
e3 = ValueError()
e1.__context__ = e2
e2.__context__ = e3
raise e1
