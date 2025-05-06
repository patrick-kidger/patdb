import argparse
import inspect
import sys
import types

from . import _core


class _PytestToPatdb:
    def __init__(self):
        self.quitting = False

    def reset(self):
        pass

    def interaction(self, _, _tb: types.TracebackType | None):
        is_stop_iteration = False
        # If you have an error during test collection, trigger this function, and then
        # `q`uit, then you actually trigger this function again internally to pytest!
        # That's clearly just a pytest bug, but we work around it here.
        # (Notably `--pdb` also triggers again -- without working around it -- so
        # nothing unique to us.)
        while _tb is not None:
            if not _core.is_frame_pytest(_tb.tb_frame):
                break
            if _tb.tb_next is None and (
                exception := _tb.tb_frame.f_locals.get("exception", None)
            ):
                if (
                    type(exception) is RuntimeError
                    and str(exception) == "generator raised StopIteration"
                ):
                    # We do need to carve out an edge case to this edge case: when the
                    # test raises a `StopIteration` specifically then we seem to end up
                    # here as well...
                    is_stop_iteration = True
                    break
            _tb = _tb.tb_next
        else:
            return  # Internal pytest error during quitting.
        # The traceback is useless to us, it doesn't have any way of getting the
        # __cause__ or __context__ of the actual exception. Just delete it.
        del _tb

        for name in ("last_exc", "last_value"):
            # This branch occurs if an error occurs during a test itself.
            # In this case, grab the exception if we can.
            try:
                e = getattr(sys, name)
            except AttributeError:
                pass
        else:
            # This branch occurs if an error occurs during test collection.
            # In this case, it's time for an awful hack.
            # Unfortunately the `_tb` argument doesn't give us what we want. So we walk
            # walk the stack and grab the thing we do want!
            # This is wrapped in a try-except just for forward compatibility, in case
            # the pytest folks ever change things.
            try:
                frame = inspect.stack()[2]
                e = frame.frame.f_locals["excinfo"].value
            except Exception:
                return
        if is_stop_iteration:  # More working around pytest bugs.
            e = e.__context__
        try:
            _core.debug(e)
        except SystemExit:
            self.quitting = True

    def set_trace(self, frame):
        del frame
        # Skip `debug`, `set_trace`, and `_pytest.debugging.pytestPDB.set_trace`.
        _core.debug(stacklevel=3)


class _Action(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        del parser, values, option_string
        namespace.usepdb = True
        namespace.usepdb_cls = (_PytestToPatdb.__module__, _PytestToPatdb.__name__)


def pytest_addoption(parser):
    group = parser.getgroup("patdb")
    group.addoption(
        "--patdb",
        action=_Action,
        nargs=0,
        help="Open a `patdb` debugger on error.",
    )


def pytest_configure(config):
    _core._pytest_pluginmanager = config.pluginmanager
