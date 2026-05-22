import inspect
import pathlib
import sys
import tempfile
from collections.abc import Sequence

import seali

from ._core import debug


def _run(filepath: str, args: Sequence[str]):
    import runpy

    sys.argv = [filepath, *args]
    __tracebackhide__ = True

    try:
        runpy.run_path(filepath, run_name="__main__")
    except BaseException as e:
        debug(e)
        sys.exit(1)


@seali.command
def run(*args: str, c: None | str = None):
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
            filepath, *args_rest = args
            _run(filepath, args_rest)
    else:
        # `python -m patdb -c 'some program' some args here`
        # We write the program to a temporary file to enable easier debugging: you
        # can see the source code.
        with tempfile.NamedTemporaryFile(suffix=".py") as f:
            pathlib.Path(f.name).write_text(c)
            _run(f.name, args)


run()
