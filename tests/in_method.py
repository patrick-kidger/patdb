class A:
    def some_method(self):
        raise ValueError("Kaboom")


A().some_method()
