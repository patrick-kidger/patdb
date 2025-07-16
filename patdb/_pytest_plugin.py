import argparse
import inspect
import os
import sys
import types

import click

from . import _core


class _PytestToPatdb:
    def __init__(self):
        self.quitting = False

    def reset(self):
        pass

    def interaction(self, _, _tb: BaseException | types.TracebackType | None):
        if isinstance(_tb, BaseException):
            # We get an exception in Python 3.13+. This is all we really want!
            # https://github.com/pytest-dev/pytest/pull/12708
            e = _tb
        else:
            # On lower Python... settle in.

            # If you have an error during test collection, trigger this function, and
            # then `q`uit, then you actually trigger this function again internally to
            # pytest!
            #
            # That's clearly just a pytest bug, and we work around it here: we iterate
            # through and check for a non-pytest frame. If they're all pytest frames
            # then we're in the bug case and we don't need to do anything.
            #
            # (Notably `--pdb` also triggers again -- without working around it -- so
            # nothing unique to us.)
            is_stop_iteration = False
            while _tb is not None:
                if not _core.is_frame_pytest(_tb.tb_frame):
                    break
                # Actually, we need to carve out an edge case to this edge case: when
                # the test raises a `StopIteration` then pytest translates that into a
                # different exception, which does have only pytest frames.
                if _tb.tb_next is None and (
                    exception := _tb.tb_frame.f_locals.get("exception", None)
                ):
                    if (
                        type(exception) is RuntimeError
                        and str(exception) == "generator raised StopIteration"
                    ):
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
                # Unfortunately the `_tb` argument doesn't give us what we want. So we
                # walk the stack and grab the thing we do want!
                frame = inspect.stack()[2]
                e = frame.frame.f_locals["excinfo"].value
            if is_stop_iteration:  # Unpack th pytest exception we detected earlier.
                e = e.__context__

        try:
            current_test = os.environ["PYTEST_CURRENT_TEST"]
        except KeyError:
            pass  # I don't think getting here is possible, but just in case.
        else:
            click.echo(" Failing test: " + _core.emph(current_test))
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
