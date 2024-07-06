class Foo(Exception):
    class Bar(Exception):
        pass


try:
    raise Foo("World")
except Exception as e:
    raise Foo.Bar("Hello") from e
