import inspect
import pathlib
import sys
import tempfile

import click

from ._core import debug


def _run(filepath: str, args: list[str]):
    import runpy

    sys.argv = [filepath, *args]
    __tracebackhide__ = True

    try:
        runpy.run_path(filepath, run_name="__main__")
    except BaseException as e:
        debug(e)
        sys.exit(1)


@click.command()
@click.option("-c")
@click.argument("args", nargs=-1)
def run(c, args):
    for frame in inspect.stack():
        frame.frame.f_locals["__tracebackhide__"] = True

    if c is None:
        if len(args) == 0:
            # Just `python -m patdb`.
            # In this case drop straight into the debugger -- useful when developing
            # `patdb` itself!
            debug()
            return
        else:
            # `python -m patdb foo.py some args here`
            filepath, *args = args
            _run(filepath, args)
    else:
        # `python -m patdb -c 'some program' some args here`
        # We write the program to a temporary file to enable easier debugging: you
        # can see the source code.
        with tempfile.NamedTemporaryFile(suffix=".py") as f:
            pathlib.Path(f.name).write_text(c)
            _run(f.name, args)


run()
