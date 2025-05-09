import bdb
import builtins
import collections as co
import contextlib
import dataclasses
import enum
import functools as ft
import gc
import importlib.machinery
import inspect
import logging
import multiprocessing
import operator
import os
import pathlib
import re
import shutil
import subprocess
import sys
import textwrap
import threading
import time
import traceback
import types
import warnings
import weakref
from collections.abc import Callable, Iterable, Iterator
from typing import (
    Any,
    Generic,
    Literal,
    NoReturn,
    overload,
    TypeGuard,
    TypeVar,
)
from typing_extensions import Self

import click
import prompt_toolkit
import prompt_toolkit.completion
import prompt_toolkit.document
import prompt_toolkit.formatted_text
import prompt_toolkit.history
import prompt_toolkit.key_binding
import prompt_toolkit.keys
import prompt_toolkit.layout
import prompt_toolkit.layout.containers
import prompt_toolkit.layout.controls
import prompt_toolkit.lexers
import prompt_toolkit.output
import prompt_toolkit.shortcuts
import prompt_toolkit.styles.pygments
import ptpython
import ptpython.completer
import ptpython.prompt_style
import pygments
import pygments.formatters
import pygments.lexers
import pygments.styles
import pygments.token
import wadler_lindig as wl


#
# Configuration
#


class _Config:
    #
    # First we have configuration for formatting: colours etc.
    #
    @ft.cached_property
    def code_style(self) -> str:
        return os.getenv("PATDB_CODE_STYLE", "solarized-dark")

    # These default colours are carefully chosen to be visible on both light and dark
    # terminal backgrounds.

    @ft.cached_property
    def emph_colour(self) -> tuple[int, int, int]:
        colour = os.getenv("PATDB_EMPH_COLOUR", os.getenv("PATDB_EMPH_COLOR", None))
        if colour is None:
            colour = "#4cb066"
        out = _hex_to_rgb(colour)
        assert out is not None
        return out

    @ft.cached_property
    def error_colour(self) -> tuple[int, int, int]:
        colour = os.getenv("PATDB_ERROR_COLOUR", os.getenv("PATDB_ERROR_COLOR", None))
        if colour is None:
            colour = "#dc322f"
        out = _hex_to_rgb(colour)
        assert out is not None
        return out

    @ft.cached_property
    def info_colour(self) -> tuple[int, int, int]:
        colour = os.getenv("PATDB_INFO_COLOUR", os.getenv("PATDB_INFO_COLOR", None))
        if colour is None:
            colour = "#888888"
        out = _hex_to_rgb(colour)
        assert out is not None
        return out

    @ft.cached_property
    def prompt_colour(self) -> tuple[int, int, int]:
        colour = os.getenv("PATDB_PROMPT_COLOUR", os.getenv("PATDB_PROMPT_COLOR", None))
        if colour is None:
            colour = "#268bd2"
        out = _hex_to_rgb(colour)
        assert out is not None
        return out

    #
    # Here we have the keys for the REPL.
    #

    @ft.cached_property
    def key_down_frame(self) -> str:
        return os.getenv("PATDB_KEY_DOWN_FRAME", "j")

    @ft.cached_property
    def key_up_frame(self) -> str:
        return os.getenv("PATDB_KEY_UP_FRAME", "k")

    @ft.cached_property
    def key_down_callstack(self) -> str:
        return os.getenv("PATDB_KEY_DOWN_CALLSTACK", "J")

    @ft.cached_property
    def key_up_callstack(self) -> str:
        return os.getenv("PATDB_KEY_UP_CALLSTACK", "K")

    @ft.cached_property
    def key_show_function(self) -> str:
        return os.getenv("PATDB_KEY_SHOW_FUNCTION", "s")

    @ft.cached_property
    def key_show_file(self) -> str:
        return os.getenv("PATDB_KEY_SHOW_FILE", "S")

    @ft.cached_property
    def key_stack(self) -> str:
        return os.getenv("PATDB_KEY_STACK", "t")

    @ft.cached_property
    def key_print(self) -> str:
        return os.getenv("PATDB_KEY_PRINT", "p")

    @ft.cached_property
    def key_print_long_arrays(self) -> str:
        return os.getenv("PATDB_KEY_PRINT_LONG_ARRAYS", "P")

    @ft.cached_property
    def key_edit(self) -> str:
        return os.getenv("PATDB_KEY_EDIT", "e")

    @ft.cached_property
    def key_interpret(self) -> str:
        return os.getenv("PATDB_KEY_INTERPRET", "i")

    @ft.cached_property
    def key_visibility(self) -> str:
        return os.getenv("PATDB_KEY_VISIBILITY", "v")

    @ft.cached_property
    def key_continue(self) -> str:
        return os.getenv("PATDB_KEY_CONTINUE", "c")

    @ft.cached_property
    def key_quit(self) -> str:
        return os.getenv("PATDB_KEY_QUIT", "q")

    @ft.cached_property
    def key_help(self) -> str:
        return os.getenv("PATDB_KEY_HELP", "?")

    #
    # Now we have the keys for `(s)how_function` and `(S)how_file`.
    #

    @ft.cached_property
    def key_show_down_line(self) -> str:
        return os.getenv("PATDB_KEY_SHOW_DOWN_LINE", "j")

    @ft.cached_property
    def key_show_up_line(self) -> str:
        return os.getenv("PATDB_KEY_SHOW_UP_LINE", "k")

    @ft.cached_property
    def key_show_left(self) -> str:
        return os.getenv("PATDB_KEY_SHOW_LEFT", "h")

    @ft.cached_property
    def key_show_right(self) -> str:
        return os.getenv("PATDB_KEY_SHOW_RIGHT", "l")

    @ft.cached_property
    def key_show_down_call(self) -> str:
        return os.getenv("PATDB_KEY_SHOW_DOWN_CALL", "J")

    @ft.cached_property
    def key_show_select(self) -> str:
        return os.getenv("PATDB_KEY_SHOW_SELECT", "c")

    @ft.cached_property
    def key_show_leave(self) -> str:
        return os.getenv("PATDB_KEY_SHOW_LEAVE", "q")

    #
    # Next up, keys for `s(t)ack`.
    #

    @ft.cached_property
    def key_stack_down_frame(self) -> str:
        return os.getenv("PATDB_KEY_STACK_DOWN_FRAME", "j")

    @ft.cached_property
    def key_stack_up_frame(self) -> str:
        return os.getenv("PATDB_KEY_STACK_UP_FRAME", "k")

    @ft.cached_property
    def key_stack_down_callstack(self) -> str:
        return os.getenv("PATDB_KEY_STACK_DOWN_CALLSTACK", "J")

    @ft.cached_property
    def key_stack_up_callstack(self) -> str:
        return os.getenv("PATDB_KEY_STACK_UP_CALLSTACK", "K")

    @ft.cached_property
    def key_stack_left(self) -> str:
        return os.getenv("PATDB_KEY_STACK_LEFT", "h")

    @ft.cached_property
    def key_stack_right(self) -> str:
        return os.getenv("PATDB_KEY_STACK_RIGHT", "l")

    @ft.cached_property
    def key_stack_visibility(self) -> str:
        return os.getenv("PATDB_KEY_STACK_VISIBILITY", "v")

    @ft.cached_property
    def key_stack_error(self) -> str:
        return os.getenv("PATDB_KEY_STACK_ERROR", "r")

    @ft.cached_property
    def key_stack_collapse_single(self) -> str:
        return os.getenv("PATDB_KEY_STACK_COLLAPSE_SINGLE", "o")

    @ft.cached_property
    def key_stack_collapse_all(self) -> str:
        return os.getenv("PATDB_KEY_STACK_COLLAPSE_ALL", "O")

    @ft.cached_property
    def key_stack_select(self) -> str:
        return os.getenv("PATDB_KEY_STACK_SELECT", "c")

    @ft.cached_property
    def key_stack_leave(self) -> str:
        return os.getenv("PATDB_KEY_STACK_LEAVE", "q")

    #
    # Now various miscellaneous things.
    #

    # Uncached, it may change as we nest.
    @property
    def depth(self) -> int:
        return int(os.getenv("PATDB_DEPTH", 0))

    @depth.setter
    def depth(self, value: int):
        os.environ["PATDB_DEPTH"] = str(value)

    @ft.cached_property
    def line_editor(self) -> str | None:
        return os.getenv("PATDB_EDITOR", None)

    @ft.cached_property
    def editor(self) -> str | None:
        return os.getenv("EDITOR", None)

    @ft.cached_property
    def colorfgbg(self) -> str | None:
        return os.getenv("COLORFGBG", None)

    @ft.cached_property
    def ptpython_config_home(self) -> str | None:
        return os.getenv("PTPYTHON_CONFIG_HOME", None)


_config = _Config()


def _hex_to_rgb(x: str) -> tuple[int, int, int] | None:
    x = _keep_fg_only(x)
    if x == "":
        return None
    else:
        x = x.removeprefix("#")
        return int(x[:2], base=16), int(x[2:4], base=16), int(x[4:], base=16)


#
# Styling
#


# https://pygments.org/docs/styledevelopment/#style-rules
def _keep_fg_only(v: str) -> str:
    v = re.sub(r"bg:#[\dabcdef]{6}", "", v)
    v = re.sub(r"border:#[\dabcdef]{6}", "", v)
    v = v.replace("bg:", "")
    v = v.replace("border:", "")
    v = v.replace("nobold", "").replace("bold", "")
    v = v.replace("noitalic", "").replace("italic", "")
    v = v.replace("nounderline", "").replace("underline", "")
    v = v.replace("noinherit", "").replace("inherit", "")
    v = v.replace("transparent", "")
    return v.strip()


# We don't try to do anything too magic and figure out the terminal background colour
# via the ANSI escape sequence. This doesn't seem to be very portable between terminals:
# https://stackoverflow.com/questions/2507337/how-to-determine-a-terminals-background-color
# As such we just check an environment variable that is sometimes set, and otherwise
# just give up.
if _config.colorfgbg is None:
    _dark_terminal_bg = None
else:
    try:
        if int(_config.colorfgbg[-1]) in {0, 1, 2, 3, 4, 5, 6, 8}:  # not 7
            _dark_terminal_bg = True
        else:
            _dark_terminal_bg = False
    except (ValueError, IndexError):
        _dark_terminal_bg = None
_OriginalPygmentsStyle = pygments.styles.get_style_by_name(_config.code_style)


# We have to remove `bold` etc. as these result in the background being incompletely
# applied.
# (I'm not sure why that should be.)
class _PygmentsStyle(_OriginalPygmentsStyle):
    styles = {k: _keep_fg_only(v) for k, v in _OriginalPygmentsStyle.styles.items()}
    # Fallback colour -- a lot of styles don't have colours specified for punctuation
    # etc, despite the fact that they do have a background colour specified!
    if styles.get(pygments.token.Token, "") == "":
        _bg = _hex_to_rgb(_OriginalPygmentsStyle.background_color)
        if _bg is None:
            _dark_bg = _dark_terminal_bg
        else:
            _dark_bg = sum(_bg) < 255 * 1.5
        if _dark_bg is None:
            # No idea what the terminal colour is, make our fallback be a
            # middle-of-the-road grey.
            styles[pygments.token.Token] = "#888888"
        elif _dark_bg:
            styles[pygments.token.Token] = "#FFFFFF"
        else:
            styles[pygments.token.Token] = "#000000"
        del _bg, _dark_bg


_pygments_lexer_cls = pygments.lexers.PythonLexer
_pygments_lexer = _pygments_lexer_cls()
_pygments_formatter = pygments.formatters.TerminalTrueColorFormatter(
    style=_PygmentsStyle
)
_prompt_lexer = prompt_toolkit.lexers.PygmentsLexer(_pygments_lexer_cls)
_prompt_style = prompt_toolkit.styles.pygments.style_from_pygments_cls(_PygmentsStyle)


def _syntax_highlight(source: str) -> str:
    outs = []
    out = pygments.highlight(source, _pygments_lexer, _pygments_formatter).rstrip()
    outs.append(out)
    # This odd state of affairs is needed to handle some spurious new lines that
    # `pygments.highlight` sometimes adds.
    for char in source[::-1]:
        if char == "\n":
            outs.append("\n")
        else:
            break
    return "".join(outs)


def _emph(x: str) -> str:
    return click.style(x, fg=_config.emph_colour, reset=False) + click.style(
        "", fg="reset", reset=False
    )


def _bold(x: str) -> str:
    return click.style(x, bold=True)


def _fn_to_name(x):
    return x.__name__.removeprefix("_")


def _echo_first_line(x: str):
    click.echo(x, nl=False)


def _echo_later_lines(x: str):
    click.echo("")
    click.echo(x, nl=False)


def _echo_newline_end_command():
    click.secho("", reset=True)


#
# Utilities
#


_T = TypeVar("_T")


class _BetterThread(threading.Thread, Generic[_T]):
    returnval: Any
    exc: BaseException

    def __init__(self, *, target: Callable[[], _T]):
        def _target():
            try:
                self.returnval = target()
            except BaseException as exc:
                self.exc = exc

        super().__init__(target=_target)

    def evaluate(self) -> _T:
        self.start()
        self.join()
        if hasattr(self, "exc"):
            raise self.exc
        elif hasattr(self, "returnval"):
            return self.returnval
        else:
            assert False


def _safe_run_in_thread(fn):
    # `_safe_run_in_thread` should be used where we don't want to re-breakpoint.
    fn = _override_breakpointhook(lambda *a, **k: None)(fn)
    # `prompt_toolkit` has some DEBUG logs that we want to suppress.
    fn = _disable_logging()(fn)
    return _BetterThread(target=fn).evaluate()


#
# Managing callstacks and frames
#


def _is_frame_frozen(frame: types.FrameType) -> bool:
    # Skip the noise from `runpy`, in particular as used in our `__main__.py`.
    return frame.f_globals.get("__loader__", None) is importlib.machinery.FrozenImporter


def is_frame_pytest(frame: types.FrameType) -> bool:
    # Skip all of the noise in pytest when using the `--patdb` flag.
    name = frame.f_globals.get("__name__", "")
    for module in ("pytest", "_pytest", "pluggy"):
        if name == module or name.startswith(f"{module}."):
            return True
    filename = frame.f_code.co_filename
    if filename == "pytest" or filename.endswith("/pytest"):
        return True
    return False


def _is_frame_hidden(frame: types.FrameType, prev_frame_hidden: bool) -> bool:
    if frame.f_code.co_name in {"<genexpr>", "<listcomp>", "<setcomp>", "<dictcomp>"}:
        # Note that we require an explicit `last_hidden` input, and do not check
        # `_is_frame_hidden(frame.f_back)`, as the latter is not necessarily set when
        # inside generators.
        return prev_frame_hidden
    else:
        # https://stackoverflow.com/questions/61550012/why-doesnt-co-varnames-return-list-of-all-the-variable-names
        local_varnames = {*frame.f_code.co_varnames, *frame.f_code.co_cellvars}
        return (
            # Do not access `frame.f_locals`! Avoids the following issue on Python
            # <3.13:
            # ```python
            # import gc
            # import weakref
            #
            # class Foo:
            #     pass
            #
            # def f():
            #     x = Foo()
            #     y = weakref.ref(x)
            #     locals()  # or access `sys._getframe().f_locals`
            #     del x
            #     gc.collect()
            #     # Python >=3.13: dead reference
            #     # Python <3.13: live reference
            #     # See https://github.com/python/cpython/issues/50366 and PEP667.
            #     print(y)
            #
            # f()
            # ```
            "__tracebackhide__" in local_varnames
            or _is_frame_frozen(frame)
            or is_frame_pytest(frame)
        )


# Pairing the frame object with the traceback `tb.tb_lineno`.
#
# Note that `tb.tb_lineno` is the same as `tb.tb_frame.f_lineno` 99% of the time... but
# not 100% of the time! When creating custom code objects without filling in their
# `co_exceptiontable` and `co_linetable` (I think it's these), then any frame with that
# code object as their `f_code` will in turn have their `f_lineno` set to `None`.
#
# (`f_lineno` exist for the sake of debuggers that jump around
# (https://docs.python.org/3/reference/datamodel.html#index-65)
# so if at some point we support line-by-line evaluation then we should consider using
# it.)
@dataclasses.dataclass(frozen=True, eq=False)
class _Frame:
    _frame: types.FrameType
    line: int
    is_hidden: bool

    @property
    def f_code(self):
        return self._frame.f_code

    @property
    def f_locals(self):
        return self._frame.f_locals

    @property
    def f_globals(self):
        return self._frame.f_globals

    # Important that these caches be `cached_property` and not `functools.cache`, as the
    # latter holds on to strong references to the `self` objects.

    @ft.cached_property
    def local_filepath(self) -> None | pathlib.Path:
        filename = self.f_code.co_filename
        filepath = pathlib.Path(filename).resolve()
        if filepath.exists():
            return filepath
        else:
            # It's possible to hit this branch in a few cases.
            #
            # - Hitting an old `__pycache__`. I've seen `__pycache__` fail to be
            #   invalidated when moving a folder, for example. (Not sure why.)
            # - If you're downloading an error from a remote execution and debugging
            #   locally. Remotely the module is available at e.g.
            #   `/root/path/to/file.py` whilst locally the module is available at e.g.
            #   `~/your_repo/path/to/file.py`. But as long as the module names match up
            #   then we might still be able to access the local version of the source
            #   code.
            # - You could maybe end up here if you're monkeying with import hooks.
            # - Maybe you're looking at something like `importlib._bootstrap`, which
            #   lies about its name but not its `__file__`.
            module_name = self.f_globals.get("__name__", None)
            if module_name is None:
                return None
            module = sys.modules.get(module_name, None)
            if module is None:
                return None
            filename = getattr(module, "__file__", None)
            if filename is None:
                return None
            filepath = pathlib.Path(filename).resolve()
            if filepath.exists():
                return filepath
            else:
                return None

    @ft.cached_property  # Cache result in case we modify the file via `(e)dit`.
    def function_source(self) -> None | list[str]:
        # This implementation is better than `inspect.getsourcelines`, in that we (a)
        # use our improved `file_source` implementation below (which is more robust to
        # bad `__pycache__`s than `inspect.getfile`) and (b) we produce the right
        # results for generators, rather than just producing their containing function.
        if self.file_source is None:
            return None
        else:
            # `max` just in case someone is doing evil things and passing nonpositive
            # line numbers around. I can't imagine an example for that, but just in
            # case?
            # -1 because line numbers start from 1.
            source = self.file_source[max(0, self.f_code.co_firstlineno - 1) :]
            source = [line + "\n" for line in source]
            if self._frame.f_code.co_name != "<module>":
                # This is the same condition used in `inspect.getsourcelines`, so
                # hopefully it's reliable.
                source = inspect.getblock(source)
            return [line.rstrip() for line in source]

    @ft.cached_property  # Cache result in case we modify the file via `(e)dit`.
    def file_source(self) -> None | list[str]:
        filepath = self.local_filepath
        if filepath is None:
            return None
        else:
            return filepath.read_text().rstrip().splitlines()

    def cache(self):
        self.local_filepath
        self.function_source
        self.file_source

    def set_trace(self, local_trace_hook) -> Callable[[], None]:
        self._frame.f_trace = local_trace_hook
        self._frame.f_trace_lines = True

        # Don't keep the frame alive just because we want to uninstall its hook! That'd
        # be superfluous.
        # We use `self` rather than `self._frame` because frames are not weakref'able.
        weak_self = weakref.ref(self)
        # Whilst we're here we also only use a weakref to the trace hook we're
        # uninstalling. This one probably matters less but seems like the right thing to
        # do.
        weak_local_trace_hook = weakref.ref(local_trace_hook)

        def uninstall_local_trace_hook():
            maybe_self = weak_self()
            maybe_hook = weak_local_trace_hook()
            if (
                maybe_self is not None
                and maybe_hook is not None
                and maybe_self._frame.f_trace is maybe_hook
            ):
                maybe_self._frame.f_trace = None

        return uninstall_local_trace_hook


class _CallstackKind(enum.Enum):
    # Order corresponds to the order printed out when we have multiple kinds.
    toplevel = 0
    group = 1
    cause = 2
    context = 3
    suppressed_context = 4


@dataclasses.dataclass(frozen=True, eq=False)
class _Callstack:
    _up_callstack: weakref.ref[Self] | None
    down_callstacks: tuple[Self, ...]
    frames: tuple[_Frame, ...]
    kinds: frozenset[_CallstackKind]
    exception: BaseException | None
    collapse_default: bool

    def __post_init__(self):
        assert len(self.kinds) != 0

    @property
    def up_callstack(self) -> Self | None:
        up_callstack = self._up_callstack
        if up_callstack is None:
            return None
        else:
            up_callstack = up_callstack()
            assert up_callstack is not None
            return up_callstack

    @property
    def kind_msg(self):
        return " + ".join(
            kind.name for kind in sorted(self.kinds, key=lambda kind: kind.value)
        )


def _next_call_trace(done_cell: list[bool], frame: types.FrameType, event: str, arg):
    del arg
    if event == "call" and done_cell[0]:
        trace = sys.gettrace()
        if type(trace) is ft.partial and trace.func is _next_call_trace:
            sys.settrace(None)
        else:
            click.echo(
                "Warning: some tool (other than `patdb`) has set `sys.settrace` whilst "
                "jumping between frames. The other tool's global trace function has "
                "been left in place, but nonetheless you may see unexpected behaviour."
            )
        debug(frame)


def _line_trace(
    line_num: int,
    uninstall_hooks: list[Callable[[], None]],
    frame: types.FrameType,
    event: str,
    arg,
):
    del arg
    if event == "line" and frame.f_lineno == line_num:
        # We've found where we need to be, so uninstall all our hooks.
        for hook in uninstall_hooks:
            hook()
        debug(frame)


def _file_trace(
    filepath: pathlib.Path,
    line_num: int,
    uninstall_hooks: list[Callable[[], None]],
    frame: types.FrameType,
    event: str,
    arg,
):
    del arg
    if event == "call" and pathlib.Path(frame.f_code.co_filename).resolve() == filepath:
        return ft.partial(_line_trace, line_num, uninstall_hooks)


def _get_callstacks_from_error(
    exception: BaseException,
    up_callstack: _Callstack | None,
    kinds: frozenset[_CallstackKind],
    collapse_default: bool,
) -> _Callstack:
    tb = exception.__traceback__
    frames: list[_Frame] = []
    frame_hidden = False
    while tb is not None:
        frame_hidden = _is_frame_hidden(tb.tb_frame, frame_hidden)
        frames.append(_Frame(tb.tb_frame, tb.tb_lineno, frame_hidden))
        tb = tb.tb_next
    callstack = _Callstack(
        _up_callstack=None if up_callstack is None else weakref.ref(up_callstack),
        down_callstacks=(),
        frames=tuple(frames),
        kinds=kinds,
        exception=exception,
        collapse_default=collapse_default,
    )
    down_callstacks = []
    # No reason that exceptions should be hashable, so using `id`.
    id_exception_to_kind = co.defaultdict(set)
    id_to_exception = {}
    if exception.__cause__ is not None:
        subexception = exception.__cause__
        id_exception_to_kind[id(subexception)].add(_CallstackKind.cause)
        id_to_exception[id(subexception)] = subexception
    if exception.__context__ is not None:
        subexception = exception.__context__
        id_exception_to_kind[id(subexception)].add(_CallstackKind.context)
        if exception.__suppress_context__:
            id_exception_to_kind[id(subexception)].add(
                _CallstackKind.suppressed_context
            )
        id_to_exception[id(subexception)] = subexception
    if hasattr(builtins, "BaseExceptionGroup") and isinstance(
        exception, BaseExceptionGroup
    ):
        for subexception in exception.exceptions:
            id_exception_to_kind[id(subexception)].add(_CallstackKind.group)
            id_to_exception[id(subexception)] = subexception

    suppress_kinds = frozenset(
        [_CallstackKind.suppressed_context, _CallstackKind.context]
    )
    for id_e, subexception in id_to_exception.items():
        kinds = frozenset(id_exception_to_kind[id_e])
        down_callstacks.append(
            _get_callstacks_from_error(
                subexception,
                up_callstack=callstack,
                kinds=kinds,
                collapse_default=collapse_default or (kinds == suppress_kinds),
            )
        )
    # "tie the knot" with some sneaky mutation, since we don't have laziness.
    # We can't use `dataclasses.replace` because our children have a reference to us!
    object.__setattr__(callstack, "down_callstacks", tuple(down_callstacks))
    return callstack


_Carry = TypeVar("_Carry")


class _CallstackNesting(enum.Enum):
    only = "only"
    earlier = "earlier"
    last = "last"


def _callstack_iter(
    callstack: _Callstack,
    carry: _Carry,
    update_carry: Callable[[_Carry, _CallstackNesting], _Carry],
    evaluate_callstack: Callable[[_Callstack, _Carry], Any],
):
    yield evaluate_callstack(callstack, carry)
    if len(callstack.down_callstacks) == 1:
        [down_callstack] = callstack.down_callstacks
        if _CallstackKind.group in down_callstack.kinds:
            # Single-group-members are displayed indented.
            down_carry = update_carry(carry, _CallstackNesting.last)
        else:
            # Normal cause/context relationships are displayed unindented.
            down_carry = update_carry(carry, _CallstackNesting.only)
        down_callstack_carries = [(down_callstack, down_carry)]
    elif len(callstack.down_callstacks) > 1:
        *earlier_down_callstacks, last_down_callstack = callstack.down_callstacks
        earlier_down_carry = update_carry(carry, _CallstackNesting.earlier)
        last_down_carry = update_carry(carry, _CallstackNesting.last)
        down_callstack_carries = [
            (earlier_down_callstack, earlier_down_carry)
            for earlier_down_callstack in earlier_down_callstacks
        ] + [(last_down_callstack, last_down_carry)]
    else:
        down_callstack_carries = []
    for down_callstack, down_carry in down_callstack_carries:
        yield from _callstack_iter(
            down_callstack,
            down_carry,
            update_carry,
            evaluate_callstack,
        )


@dataclasses.dataclass(frozen=True, eq=False)
class _Location:
    callstack: _Callstack
    frame_idx: int | None

    def __post_init__(self):
        if len(self.callstack.frames) == 0:
            assert self.frame_idx is None
        else:
            assert self.frame_idx is not None
            assert 0 <= self.frame_idx < len(self.callstack.frames)


def _current_frame(location: _Location) -> str | _Frame:
    if location.frame_idx is None:
        return "<Frameless callstack>"
    else:
        return location.callstack.frames[location.frame_idx]


@dataclasses.dataclass(frozen=True)
class _MoveLocation:
    location: _Location
    num_hidden: int


def _move_frame(
    location: _Location,
    *,
    skip_hidden: bool,
    down: bool,
    include_current_location: bool,
) -> _MoveLocation:
    if location.frame_idx is None:
        del skip_hidden, down
        # Just stay where we are
        return _MoveLocation(location, 0)
    else:
        i_frames = list(enumerate(location.callstack.frames))
        if down:
            if include_current_location:
                i_frames = i_frames[location.frame_idx :]
            else:
                i_frames = i_frames[location.frame_idx + 1 :]
        else:
            if include_current_location:
                i_frames = list(reversed(i_frames[: location.frame_idx + 1]))
            else:
                i_frames = list(reversed(i_frames[: location.frame_idx]))
        num_hidden = 0
        for frame_idx_out, frame in i_frames:
            if skip_hidden and frame.is_hidden:
                num_hidden += 1
            else:
                return _MoveLocation(
                    _Location(location.callstack, frame_idx_out), num_hidden
                )
        else:
            assert num_hidden == len(i_frames)
            return _MoveLocation(location, num_hidden)


def _move_callstack(
    root_callstack: _Callstack,
    location: _Location,
    skip_hidden: bool,
    down: bool,
) -> _MoveLocation:
    prev_callstack = None
    callstack_iter = _callstack_iter(
        root_callstack,
        None,
        lambda carry, _: carry,
        lambda callstack, _: callstack,
    )
    for callstack in callstack_iter:
        if callstack is location.callstack:
            break
        prev_callstack = callstack
    if down:
        new_callstack = next(callstack_iter, None)
    else:
        new_callstack = prev_callstack
    if new_callstack is None:
        # we're at a top or bottom callstack.
        return _MoveLocation(location, 0)
    elif len(new_callstack.frames) == 0:
        new_location = _Location(new_callstack, None)
    else:
        if down:
            new_location = _Location(new_callstack, 0)
        else:
            new_location = _Location(new_callstack, len(new_callstack.frames) - 1)
    # Find the first non-hidden frame.
    return _move_frame(
        new_location, skip_hidden=skip_hidden, down=down, include_current_location=True
    )


@dataclasses.dataclass(frozen=True)
class _State:
    done: bool
    skip_hidden: bool
    location: _Location
    done_cell: list[bool]
    print_history: prompt_toolkit.history.InMemoryHistory
    helpmsg: Callable[[], str]
    root_callstack: _Callstack
    depth: int
    modified_files: frozenset[pathlib.Path]


#
# Ptpython (used for `i`nterpret).
#


def _check_list_of_tuples(x) -> TypeGuard[list[tuple[str, str]]]:
    if not isinstance(x, list):
        return False
    for xi in x:
        if not isinstance(xi, tuple):
            return False
        if len(xi) != 2:
            return False
        a, b = xi
        if not isinstance(a, str) or not isinstance(b, str):
            return False
    return True


class _IndentPrompt(ptpython.prompt_style.PromptStyle):
    def __init__(self, depth: int, prompt: ptpython.prompt_style.PromptStyle):
        self.depth = str(depth)
        self.prompt = prompt

    def in_prompt(self):
        in_prompt = self.prompt.in_prompt()
        if not _check_list_of_tuples(in_prompt):
            raise NotImplementedError(f"patdb does not support {self.prompt}")
        out: list[prompt_toolkit.formatted_text.OneStyleAndTextTuple] = [
            (style, self.depth + (prompt)) for style, prompt in in_prompt
        ]
        return out

    def in2_prompt(self, width: int):
        in2_prompt = self.prompt.in2_prompt(width)
        if not _check_list_of_tuples(in2_prompt):
            raise NotImplementedError(f"patdb does not support {self.prompt}")
        out: list[prompt_toolkit.formatted_text.OneStyleAndTextTuple] = [
            (style, " " * len(self.depth) + prompt) for style, prompt in in2_prompt
        ]
        return out

    def out_prompt(self):
        out_prompt = self.prompt.out_prompt()
        if not _check_list_of_tuples(out_prompt):
            raise NotImplementedError(f"patdb does not support {self.prompt}")
        out: list[prompt_toolkit.formatted_text.OneStyleAndTextTuple] = [
            (style, " " * len(self.depth) + prompt) for style, prompt in out_prompt
        ]
        return out


# We disable logging in a few places where the libraries are calling produce log output.
# In practice we assume that our debugger is robust. We would like all logging to come
# only from the user's code.
@contextlib.contextmanager
def _disable_logging():
    level = logging.root.manager.disable
    logging.disable(logging.INFO)
    try:
        yield
    finally:
        logging.disable(level)


@contextlib.contextmanager
def _disable_jedi_warnings():
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", module="jedi")
        yield


@contextlib.contextmanager
def _disable_imports():
    meta_path = sys.meta_path
    sys.meta_path = []
    # This `initializing_modules` trickery is pretty evil.
    # The problem is that `ptpython` (via `i`nterpret) or `prompt_toolkit` (via `p`rint)
    # use Jedi for completions, and this will attempt to dynamically import modules.
    # If that module is itself currently being imported (because you have a module-level
    # breakpoint) then this will cause a deadlock.
    # The solution is to pretend that it's already fully imported.
    initializing_modules = set()
    for mod in sys.modules.values():
        if inspect.getattr_static(
            inspect.getattr_static(mod, "__spec__", None), "_initializing", False
        ):
            del mod.__spec__._initializing  # pyright: ignore
            initializing_modules.add(mod)
    try:
        yield
    finally:
        for mod in initializing_modules:
            mod.__spec__._initializing = True
        sys.meta_path = meta_path


@contextlib.contextmanager
def _override_breakpointhook(hook):
    breakpointhook = sys.breakpointhook
    sys.breakpointhook = hook
    try:
        yield
    finally:
        sys.breakpointhook = breakpointhook


class _SafeCompleter(prompt_toolkit.completion.Completer):
    # I found a case where completions raise spurious errors when trying to import a
    # module that cannot be imported.

    def __init__(self, completer: prompt_toolkit.completion.Completer):
        self.completer = completer

    def get_completions(
        self,
        document: prompt_toolkit.document.Document,
        complete_event: prompt_toolkit.completion.CompleteEvent,
    ) -> Iterable[prompt_toolkit.completion.Completion]:
        # ptpython uses a local import of jedi, so get that done now before we disable
        # imports.
        import jedi
        import jedi.inference.finder
        import jedi.inference.star_args

        del jedi

        with (
            # We don't ever want breakpoints to trigger when getting completions, so we
            # disable it.
            _override_breakpointhook(lambda *a, **k: None),
            # Silence noisy debug logs from prompt_toolkit.
            _disable_logging(),
            # Prevent Jedi from dynamically performing imports. We're using a debugger
            # here, so silently screwing with `sys.modules` is pretty confusing!
            _disable_imports(),
            # Prevent Jedi from complaining about any nonimportable modules, with
            # warnings of the form 'Module foo is not importable in path ...'.
            _disable_jedi_warnings(),
        ):
            try:
                iter_completions = iter(
                    self.completer.get_completions(document, complete_event)
                )
            except Exception:
                return
            # Don't get completions element-by-element but collect them into a list,
            # so that we don't need to keep flip-flopping through our `with`
            # statements above.
            completions = []
            while True:
                try:
                    completions.append(next(iter_completions))
                except StopIteration:
                    break
                except Exception:
                    # Something went wrong. Probably we're in some kind of broken
                    # environment, for which Jedi cannot dynamically import in order to
                    # find its completions.
                    pass
        # Unindented, to close out the `with` statement.
        yield from completions


class _PythonReplNoSave(ptpython.repl.PythonRepl):
    # We prevent the interactive Python REPL from saving the last value.
    # This is because it then persists forever, in particular appearing in
    # `gc.get_referrers`. This is a tool that we like to use when debugging, so
    # disabling the noise here is more important than keeping a value around.
    def _store_eval_result(self, result):
        del result


def _ptpython_configure(repl: ptpython.repl.PythonRepl):
    config = _config.ptpython_config_home
    if config is not None and os.path.exists(config):
        ptpython.repl.run_config(repl, config)
    if _config.depth is not None:
        for k, v in list(repl.all_prompt_styles.items()):
            repl.all_prompt_styles[k] = _IndentPrompt(_config.depth, v)
    repl.completer = _SafeCompleter(repl.completer)
    repl.__class__ = _PythonReplNoSave


_patdb_history_file = pathlib.Path.home() / ".cache" / "patdb" / "history"
_patdb_history_file.parent.mkdir(parents=True, exist_ok=True)
_patdb_history_file.touch()


#
# Implementations for the REPL and its commands
#

_ansi_re = re.compile(r"(\x1b\[[;?0-9]*[a-zA-Z])")  # stolen from `click.unstyle`


def _format_text_for_basic_app(
    text: list[str], hscroll: int
) -> list[prompt_toolkit.formatted_text.OneStyleAndTextTuple]:
    scrolled_text: list[str] = []
    for line in text:
        wrapped_line: list[str] = []
        line_hscroll = hscroll
        for piece in _ansi_re.split(line):
            if _ansi_re.match(piece) is None and piece != "":
                if line_hscroll > len(piece):
                    line_hscroll -= len(piece)
                else:
                    piece = piece[line_hscroll:]
                    line_hscroll = 0
                    wrapped_line.append(piece)
            else:
                wrapped_line.append(piece)
        scrolled_text.append("".join(wrapped_line))

    formatted_text: list[prompt_toolkit.formatted_text.OneStyleAndTextTuple] = [
        ("[ZeroWidthEscape]", "\r")
    ]
    for line in scrolled_text:
        formatted_text.append(("[ZeroWidthEscape]", "\x1b[2K"))  # erase entire line

        # fill background + move cursor to right edge of screen: the newline doesn't get
        # the background colour for some reason, so we punt it to the right edge of the
        # screen.
        formatted_text.append(("[ZeroWidthEscape]", line))
        formatted_text.append(("[ZeroWidthEscape]", "\x1b[K\x1b[1000C"))
        formatted_text.append(("", "\n"))  # separate so the last one can be popped.
    if len(formatted_text) > 0:
        formatted_text.pop()
    return formatted_text


def _basic_app(
    initial_carry: _Carry,
    display: Callable[[_Carry], list[str]],
    key_mapping: dict[
        Callable[[_Carry], tuple[_Carry, bool]] | Literal["left", "right"],
        tuple[str, str | None],
    ],
    depth: int,
) -> _Carry:
    carry = initial_carry
    hscroll = 0
    initial_text = display(initial_carry)
    max_width = max(len(click.unstyle(line)) for line in initial_text)

    new_key_mapping = {}
    for k, v in key_mapping.items():

        def new_k(event, k=k):
            nonlocal carry, hscroll
            if k == "left":
                hscroll = max(0, hscroll - 5)
                done = False
            elif k == "right":
                hscroll = min(hscroll + 5, max_width)
                done = False
            else:
                assert callable(k)
                carry, done = k(carry)
            event.app.layout.container.content.text = _format_text_for_basic_app(
                display(carry), hscroll
            )
            event.app.reset()
            if done:
                event.app.exit()

        new_key_mapping[new_k] = v
    del key_mapping

    key_bindings, fn_keys, errors = _make_key_bindings(
        {k: v for k, (v, _) in new_key_mapping.items()}, depth
    )
    for error in errors:
        _echo_later_lines(error)

    container = prompt_toolkit.layout.containers.Window(
        content=prompt_toolkit.layout.controls.FormattedTextControl(
            text=_format_text_for_basic_app(initial_text, 0), show_cursor=False
        ),
        # `wrap_lines=True` doesn't seem to work? It's not such a big deal, scrolling
        # horizontally is arguably more readable anyway.
        wrap_lines=False,
        # For some reason we need a dummy style here to get this to print correctly.
        style="class:foo",
    )
    layout = prompt_toolkit.layout.Layout(container)
    output = prompt_toolkit.output.create_output()
    if hasattr(output, "enable_cpr"):
        output.enable_cpr = False  # pyright: ignore[reportAttributeAccessIssue]
    app = prompt_toolkit.Application(
        full_screen=False,
        layout=layout,
        key_bindings=key_bindings,
        include_default_pygments_style=False,
        output=output,
    )
    infos = ["Press "]
    for i, (command, (_, info)) in enumerate(new_key_mapping.items()):
        keys = "/".join(fn_keys[command])
        infos.append(keys)
        if info is None:
            infos.append(", ")
        else:
            infos.append(f" {info}")
            if i == len(new_key_mapping) - 1:
                infos.append(".")
            else:
                infos.append("; ")
    _echo_later_lines(_patdb_info("".join(infos), depth))
    click.echo("")
    _safe_run_in_thread(app.run)
    return carry


# Note that we must not cache the result of this function, as else nested `patdb`
# instances will not pick up on the correct depth.
def _patdb_prompt(depth: int) -> str:
    """The REPL command prompt."""
    if depth == 0:
        prompt = "patdb> "
    else:
        prompt = f"patdb{depth}> "
    return click.style(prompt, fg=_config.prompt_colour)


def _patdb_info(x: str | list[str], depth: int):
    """Used to display information about `patdb` itself, e.g. command hints.

    Should NOT be used to display information about the current session state, e.g.
    stack locations.
    """
    if depth == 0:
        prompt = "patdb: "
    else:
        prompt = f"patdb{depth}: "
    if isinstance(x, str):
        xs = x.splitlines()
    else:
        xs = x
    xs = [prompt + xi for xi in xs]
    return click.style("".join(xs), fg=_config.info_colour)


def _make_key_bindings(key_mapping: dict[Callable, str], depth: int):
    errors = []
    key_bindings = prompt_toolkit.key_binding.KeyBindings()
    fn_keys = {}
    keys_fn = {}
    for fn, keys in key_mapping.items():
        if len(keys) == 0:
            continue
        fn_keys[fn] = []
        for key in keys.split("/"):
            try:
                existing_fn = keys_fn[key]
            except KeyError:
                pass
            else:
                errors.append(
                    _patdb_info(
                        f"Misconfigured `patdb`. `{key}` is being used for both "
                        f"`{_fn_to_name(existing_fn)}` and `{_fn_to_name(fn)}`. "
                        f"Keeping just `{_fn_to_name(existing_fn)}`.",
                        depth,
                    )
                )
                continue

            fn_keys[fn].append(key)
            keys_fn[key] = fn
            try:
                key_bindings.add(*key.split("+"))(fn)
            except ValueError:
                errors.append(
                    _patdb_info(
                        f"Misconfigured `patdb`. `{key}` is not a valid command.", depth
                    )
                )
    return key_bindings, fn_keys, errors


def _make_arrow(*, current: bool, interactive: bool) -> str:
    if current:
        arrow1 = "-"
    else:
        arrow1 = " "
    if interactive:
        arrow2 = ">"
    else:
        arrow2 = " "
    return arrow1 + arrow2


def _error_pieces(x: str) -> str:
    return ".".join(click.style(m, fg=_config.error_colour) for m in x.split("."))


def _format_exception(e: BaseException, short: bool) -> list[str]:
    qualname = _error_pieces(e.__class__.__qualname__)
    if e.__class__.__module__ == "builtins":
        coloured_module = "builtins"
    else:
        coloured_module = _error_pieces(e.__class__.__module__)
    if short:
        if coloured_module == "builtins":
            return [qualname]
        else:
            return [".".join((coloured_module, qualname))]
    else:
        coloured_e = type(e.__class__.__name__, (e.__class__,), {})
        coloured_e.__name__ = click.style(e.__class__.__name__, fg=_config.error_colour)
        coloured_e.__qualname__ = qualname
        coloured_e.__module__ = coloured_module
        formatter = traceback.TracebackException(coloured_e, e, None, compact=True)
        values = []
        for piece in formatter.format_exception_only():
            for line in piece.splitlines():
                values.append(line)
        if isinstance(e, SyntaxError):
            # Strip `File "<stdin>", line 1`.
            values = values[1:]
            # Dedent the needless indent.
            values = textwrap.dedent("".join(values[:-1])).splitlines() + [values[-1]]
        return [line.rstrip() for line in values]


def _format_frame(frame: _Frame, prefix: str | None = None) -> str:
    file = frame.f_code.co_filename
    if file.startswith("/"):
        if prefix is not None:
            file = file.removeprefix(prefix)
    elif not file.startswith("<"):
        file = "./" + file
    # co_qualname is Python 3.11+
    try:
        name = frame.f_code.co_qualname
    except AttributeError:
        name = frame.f_code.co_name
    current_line = str(frame.line)
    function_line = str(frame.f_code.co_firstlineno)
    if frame.is_hidden:
        lbr = "("
        rbr = ")"
    else:
        lbr = " "
        rbr = " "
    return (
        f"{lbr}File {_emph(file)}, at {_emph(name)} from {_emph(function_line)}, "
        f"line {_emph(current_line)}{rbr}"
    )


def _format_callstack(
    callstack: _Callstack,
    interactive_location: _Location | None,
    current_location: _Location | None,
    skip_hidden: bool,
    short: bool,
    is_collapsed: Callable[[_Callstack], bool],
    first_indent: str,
    indent: str,
    last_indent: str,
    nesting: _CallstackNesting,
) -> Iterator[tuple[str, bool]]:
    foldernames = []
    frame_lines = []
    num_hidden_frames = 0

    # Iterate through all of one callstack. We need to do this to count the number
    # of hidden frames, and figure out its prefix.
    if interactive_location is None:
        assert current_location is None
        is_current_callstack = False
        is_interactive_callstack = False
        current_frame_idx = None
        interactive_frame_idx = None
    else:
        assert current_location is not None
        is_current_callstack = current_location.callstack is callstack
        is_interactive_callstack = interactive_location.callstack is callstack
        current_frame_idx = current_location.frame_idx
        interactive_frame_idx = interactive_location.frame_idx
    if is_collapsed(callstack):
        is_hidden_callstack = True
    else:
        if len(callstack.frames) == 0:
            is_hidden_callstack = False
        else:
            is_hidden_callstack = True
        for j, frame in enumerate(callstack.frames):
            is_hidden_frame = frame.is_hidden
            if is_hidden_frame:
                num_hidden_frames += 1
            is_current_frame = is_current_callstack and j == current_frame_idx
            is_interactive_frame = (
                is_interactive_callstack and j == interactive_frame_idx
            )
            if (
                is_current_frame
                or is_interactive_frame
                or not (skip_hidden and is_hidden_frame)
            ):
                if frame.f_code.co_filename.startswith("/"):
                    foldernames.append(frame.f_code.co_filename)
                frame_lines.append(
                    (frame, is_current_frame, is_interactive_frame, is_hidden_frame)
                )
                is_hidden_callstack = False

    if len(foldernames) == 0:
        prefix = ""
    else:
        prefix = pathlib.Path(os.path.commonpath(foldernames))
        if prefix.is_file():
            prefix = str(prefix.parent) + "/"
        elif str(prefix) == "/":
            prefix = ""
        else:
            prefix = str(prefix) + "/"
    del foldernames

    no_frames = len(frame_lines) == 0
    if no_frames:
        callstack_arrow = _make_arrow(
            current=is_current_callstack, interactive=is_interactive_callstack
        )
    else:
        callstack_arrow = "  "
    if nesting == _CallstackNesting.only:
        callstack_linker = " "
    else:
        callstack_linker = "─"
    if is_hidden_callstack:
        callstack_line = (
            callstack_arrow
            + first_indent
            + callstack_linker
            + _bold(f"({callstack.kind_msg} callstack with all frames hidden)")
        )
    else:
        callstack_line = (
            callstack_arrow
            + first_indent
            + callstack_linker
            + _bold(f"{callstack.kind_msg} callstack")
        )
    yield callstack_line, is_interactive_callstack and no_frames
    if not is_hidden_callstack:
        if prefix != "":
            yield f"  {indent}" + _bold(f" prefix: {prefix}"), False
        if num_hidden_frames != 0:
            yield (
                f"  {indent}" + _bold(f" number of hidden frames: {num_hidden_frames}"),
                False,
            )
        for (
            frame,
            is_current_frame,
            is_interactive_frame,
            is_hidden_frame,
        ) in frame_lines:
            frame_arrow = _make_arrow(
                current=is_current_frame, interactive=is_interactive_frame
            )
            frame_str = _format_frame(frame, prefix)
            stack_line = f"{frame_arrow}{indent}{frame_str}"
            if is_interactive_frame or is_current_frame:
                stack_line = _bold(stack_line)
            yield stack_line, is_interactive_frame
        if callstack.exception is not None:
            e_lines = _format_exception(callstack.exception, short)
            for line in e_lines[:-1]:
                yield f"  {indent} {line}", False
            if len(callstack.down_callstacks) == 0:
                final_indent = last_indent
            else:
                final_indent = indent
            yield f"  {final_indent} {e_lines[-1]}", False


def _format_callstacks(
    root_callstack: _Callstack,
    interactive_location: _Location,
    current_location: _Location,
    is_collapsed: Callable[[_Callstack], bool],
    skip_hidden: bool,
    short: bool,
) -> Iterator[tuple[str, bool]]:
    carry = ("│", "│", "╵", _CallstackNesting.only)

    def update_indent(
        carry: tuple[str, str, str, _CallstackNesting],
        callstack_nesting: _CallstackNesting,
    ) -> tuple[str, str, str, _CallstackNesting]:
        _, indent, last_indent, _ = carry
        if callstack_nesting == _CallstackNesting.only:
            return indent, indent, last_indent, _CallstackNesting.only
        elif callstack_nesting == _CallstackNesting.earlier:
            return (
                indent + " ├",
                indent + " │",
                indent + " │",
                _CallstackNesting.earlier,
            )
        elif callstack_nesting == _CallstackNesting.last:
            return (
                indent + " ├",
                indent + " │",
                last_indent + " ╵",
                _CallstackNesting.last,
            )
        else:
            assert False

    def callstack_info(
        callstack: _Callstack, carry: tuple[str, str, str, _CallstackNesting]
    ):
        first_indent, indent, last_indent, nesting = carry
        return _format_callstack(
            callstack,
            interactive_location,
            current_location,
            skip_hidden,
            short,
            is_collapsed,
            first_indent,
            indent,
            last_indent,
            nesting,
        )

    for callstack_info_iterable in _callstack_iter(
        root_callstack, carry, update_indent, callstack_info
    ):
        yield from callstack_info_iterable


def _window_text(iterator: Iterator[tuple[str, bool]], ellipsis: str) -> list[str]:
    """Builds the text that is displayed by the `_s(t)ack` command."""

    # First get the terminal height to figure out the maximum amount of text we actually
    # want to output. We reduce it just so that we don't take up all the screen real
    # estate, which can be a bit much otherwise.
    terminal_height = max(1, 2 * shutil.get_terminal_size().lines // 3)
    # We'll store our outputs in a deque, which will efficiently drop earlier outputs
    # that we don't actually want to keep.
    outs = co.deque(maxlen=terminal_height)
    # We'll want to stop iterating once we get a certain amount past the stack our `>`
    # interaction marker is currently at.
    its_the_final_countdown: int | None = None

    first_line = None
    for line, is_interactive in iterator:
        if first_line is None:
            first_line = line
        if its_the_final_countdown is not None:
            its_the_final_countdown -= 1
            if its_the_final_countdown < 0:
                break
        outs.append(line)
        if is_interactive:
            assert its_the_final_countdown is None
            its_the_final_countdown = max(
                terminal_height - len(outs), terminal_height // 2
            )

    if outs[0] is not first_line:
        outs[0] = ellipsis
    if its_the_final_countdown is not None and its_the_final_countdown < 0:
        # We should never have `its_the_final_countdown is None` in well-formed input
        # data: in particular, line numbers should always be valid.
        # In practice there's nothing really stopping you from creating frames or
        # tracebacks with completely arbitrary line numbers! That might mean our
        # iterators never find the interactive line, so that `is_interactive` is always
        # `False`, and so `its_the_final_countdown` is never set. In order to be robust
        # to such wacky hackery, we do at the least just not error out in this case.
        outs[-1] = ellipsis
    return list(outs)


@dataclasses.dataclass(frozen=True)
class _StackState:
    location: _Location
    skip_hidden: bool
    update_location: bool
    short_error: bool
    is_callstack_collapsed: dict


def _format_source(
    source: str, first_line_num: int, current_line_num: int, interactive_line_num: int
) -> Iterator[tuple[str, bool]]:
    syntax_split = _syntax_highlight(source.replace("\t", "    ")).split("\n")

    max_line_num = first_line_num + len(syntax_split) - 1
    len_num = len(str(max_line_num))

    _colour_lookup = ft.cache(_hex_to_rgb)
    for i, syntax_i in enumerate(syntax_split):
        num = i + first_line_num
        if num == current_line_num:
            fg_ln = _colour_lookup(_PygmentsStyle.line_number_special_color)
            bg_ln = _colour_lookup(_PygmentsStyle.line_number_special_background_color)
            bg_line = _colour_lookup(_PygmentsStyle.highlight_color)
            arrow1 = click.style("-", bg=bg_line, reset=False)
        else:
            fg_ln = _colour_lookup(_PygmentsStyle.line_number_color)
            bg_ln = _colour_lookup(_PygmentsStyle.line_number_background_color)
            bg_line = _colour_lookup(_PygmentsStyle.background_color)
            arrow1 = click.style(" ", bg=bg_line, reset=False)
        is_interactive = num == interactive_line_num
        if is_interactive:
            arrow2 = click.style(">", bg=bg_line, reset=False)
        else:
            arrow2 = click.style(" ", bg=bg_line, reset=False)
        ln = click.style(f"{{:{len_num}}}".format(num), fg=fg_ln, bg=bg_ln, reset=False)
        line = click.style(syntax_i, bg=bg_line, reset=False)
        yield f"{arrow1}{arrow2}{ln}{line}", is_interactive


def _show_source(
    source: list[str], first_line_num: int, current_line_num: int, depth: int
) -> tuple[int | None, bool]:
    joined_source = "\n".join(source)
    last_line_num = first_line_num + len(source) - 1
    fg_ln = _hex_to_rgb(_PygmentsStyle.line_number_color)
    bg_ln = _hex_to_rgb(_PygmentsStyle.line_number_background_color)
    bg_line = _hex_to_rgb(_PygmentsStyle.background_color)

    def _display(carry: tuple[int | None, bool]) -> list[str]:
        interactive_line_num, _ = carry
        if interactive_line_num is None:
            interactive_line_num = current_line_num
        return _window_text(
            _format_source(
                joined_source, first_line_num, current_line_num, interactive_line_num
            ),
            ellipsis=click.style("  ", bg=bg_line)
            + click.style("...", fg=fg_ln, bg=bg_ln)
            + click.style("", bg=bg_line, reset=False),
        )

    def _show_up_line(
        carry: tuple[int | None, bool],
    ) -> tuple[tuple[int | None, bool], bool]:
        interactive_line_num, _ = carry
        assert interactive_line_num is not None
        return (max(first_line_num, interactive_line_num - 1), False), False

    def _show_down_line(
        carry: tuple[int | None, bool],
    ) -> tuple[tuple[int | None, bool], bool]:
        interactive_line_num, _ = carry
        assert interactive_line_num is not None
        return (min(last_line_num, interactive_line_num + 1), False), False

    def _show_down_call(
        carry: tuple[int | None, bool],
    ) -> tuple[tuple[int | None, bool], bool]:
        del carry
        return (None, True), True

    def _show_select(
        carry: tuple[int | None, bool],
    ) -> tuple[tuple[int | None, bool], bool]:
        interactive_line_num, _ = carry
        assert interactive_line_num is not None
        return (interactive_line_num, True), True

    def _show_leave(
        carry: tuple[int | None, bool],
    ) -> tuple[tuple[int | None, bool], bool]:
        interactive_line_num, _ = carry
        assert interactive_line_num is not None
        return (interactive_line_num, False), True

    key_mapping: dict = {
        _show_down_line: (_config.key_show_down_line, None),
        _show_up_line: (_config.key_show_up_line, "to scroll"),
        "left": (_config.key_show_left, None),
        "right": (_config.key_show_right, "to move view left/right"),
        _show_down_call: (
            _config.key_show_down_call,
            "to resume execution until the next function call",
        ),
        _show_select: (
            _config.key_show_select,
            "to resume execution until the selected line",
        ),
        _show_leave: (_config.key_show_leave, "to leave show mode"),
    }

    return _basic_app((current_line_num, False), _display, key_mapping, depth)


def _show_line(frame: _Frame) -> str | None:
    # Uses the file source, and not function source, because otherwise we get incorrect
    # results for generators: https://github.com/python/cpython/issues/121331
    if frame.file_source is None:
        return None
    else:
        try:
            # -1 because line numbering starts from 1 but lists are index from 0.
            source_line = frame.file_source[frame.line - 1]
        except IndexError:
            # This can happen if the source file is modified between program start and
            # when the source code is accessed now.
            return None
        else:
            [(source_line, _)] = _format_source(
                source_line, frame.line, frame.line, frame.line
            )
            return source_line + "\x1b[K"


def _install_trace(
    filepath: pathlib.Path, jump_line_num: int | None, state: _State
) -> _State:
    if sys.gettrace() is None:
        if jump_line_num is None:
            # Jump inside the next call
            sys.settrace(ft.partial(_next_call_trace, state.done_cell))
        else:
            # Jump to a higher stack frame.

            # This is slightly finickity in that we need to install several hooks.
            # We need to install:
            # - frame-local trace hooks into all current frames (that have the right
            #   `filepath`), as the global trace hook won't trigger for already-created
            #   frames.
            # - a global trace hook, in case new frames (with the right `filepath`) are
            #   created later. Any kind of global trace hook is *also* needed to trigger
            #   local trace hooks. (Otherwise the Python intepreter doesn't call them
            #   at all.)
            #
            # Once we've found where we want to be then we want to uninstall all of the
            # hooks. So we create a mutable `uninstall_hooks` list that every hook has
            # a reference to. Once any of them trigger, they are all uninstalled.

            uninstall_hooks = []
            global_hook = ft.partial(
                _file_trace, filepath, jump_line_num, uninstall_hooks
            )
            sys.settrace(global_hook)
            # Avoid keeping a strong reference to `global_hook`. Probably not important
            # but the only thing the uninstaller does is to remove it, so it seems like
            # good manners.
            weak_global_hook = weakref.ref(global_hook)

            def uninstall_global_hook():
                maybe_global_hook = weak_global_hook()
                if (
                    maybe_global_hook is not None
                    and sys.gettrace() is maybe_global_hook
                ):
                    # In principle someone else may have modified the global trace hook
                    # in between the `_file_trace` installing the local trace hook, and
                    # the local trace hook triggering.
                    # So we only uninstall the global one if it's actually ours.
                    # Otherwise we just skip it.
                    sys.settrace(None)

            uninstall_hooks.append(uninstall_global_hook)

            def install_local_hook(f: _Frame):
                local_hook = ft.partial(_line_trace, jump_line_num, uninstall_hooks)
                uninstall_hooks.append(f.set_trace(local_hook))

            _apply_to_frames_with_path(
                state.root_callstack, filepath, install_local_hook
            )
        return dataclasses.replace(state, done=True)
    else:
        _echo_first_line(
            _patdb_info(
                "The Python runtime already has a global trace function "
                "enabled, perhaps from some other tool? Cannot jump to "
                "other frames.",
                state.depth,
            )
        )
        _echo_newline_end_command()
        return state


def _update_and_display_move(
    move: _MoveLocation,
    state: _State,
    limit_msg: str,
    hidden_msg: str,
    frameless_msg: str,
) -> _State:
    if move.location is state.location:
        if move.num_hidden == 0:
            msg = limit_msg
        else:
            msg = hidden_msg.format(num_hidden=move.num_hidden)
    else:
        frame = _current_frame(move.location)
        if isinstance(frame, str):
            msg = frameless_msg
        else:
            msg = _format_frame(frame)
        state = dataclasses.replace(state, location=move.location)
    _echo_first_line(msg)
    frame = _current_frame(state.location)
    if not isinstance(frame, str):
        # If it's a string then we're in a frameless callstack, and our existing
        # `frameless_msg` applies.
        source_line = _show_line(frame)
        if source_line is None:
            source_line = "<no source found>"
        _echo_later_lines(source_line)
    _echo_newline_end_command()
    return state


def _make_namespaces(state: _State) -> tuple[dict[str, Any], dict[str, Any]]:
    frame = _current_frame(state.location)
    assert not isinstance(frame, str)
    # Create and update a new globals. This is needed (as compared to just passing
    # `frame.f_globals` directly) because `embed` sets `globals['get_ptpython']` on
    # entry and deletes it on exit. However if we are nested inside another
    # `ptpython` instance at the same time, then we may already have a
    # `get_ptpython` set! So we should create a new namespace, so we don't delete
    # the previous-level `ptpython`. (Otherwise when we quit out of *that* level, a
    # `KeyError` will be thrown in the interpreter!)
    globals = dict(frame.f_globals)
    # Fix for https://github.com/prompt-toolkit/ptpython/issues/581
    globals["exit"] = sys.exit
    globals["quit"] = sys.exit
    globals["__frame__"] = frame._frame
    if state.location.callstack.exception is not None:
        globals["__exception__"] = state.location.callstack.exception
    # Need to merge them so that name list comprehensions work. Basically we make our
    # frame be our brand-new global location in which to evaluate everything.
    globals.update(frame.f_locals)
    locals = {}
    return globals, locals


def _pprint(state: _State, short_arrays: bool) -> _State:
    frame = _current_frame(state.location)
    if isinstance(frame, str):
        _echo_first_line(frame)
        _echo_newline_end_command()
        return state
    # Make a copy to avoid mutating `state`.
    history = prompt_toolkit.history.InMemoryHistory(
        list(reversed(list(state.print_history.load_history_strings())))
    )
    globals, locals = _make_namespaces(state)
    # When using autocompletion then prompt_toolkit insists on starting at the start
    # of the line. I decided not to fight this battle, and insert a newline just to
    # avoid overwriting the `patdb>` prompt.
    _echo_first_line("\n")
    # When (a) running on Unix (Windows is still untested) and (b) using `ptpython`
    # as our top-level Python interpreter, then the first couple of `p` evaluations
    # will actually overwrite the `patdb>` prompt! (But not later ones, weirdly.)
    #
    # Here's a MWE using just `prompt_toolkit` that also works using just default
    # `python` (no `ptpython` required):
    #
    # ```python
    # import prompt_toolkit
    # print("hi", end=""); prompt_toolkit.prompt("foo?")
    # ```
    #
    # After much debugging it turns out to be linked to making cursor position
    # requests. So we disable those.
    # I think this is probably the best way to do that, but for what it's worth
    # there is also a `PROMPT_TOOLKIT_NO_CPR=1` environment variable we could use
    # instead.
    output = prompt_toolkit.output.create_output()
    if hasattr(output, "enable_cpr"):
        output.enable_cpr = False  # pyright: ignore[reportAttributeAccessIssue]
    # Note that we do *not* set the cursor: we want to keep using whatever default
    # someone is already using.
    session = prompt_toolkit.PromptSession(
        message="",
        history=history,
        lexer=_prompt_lexer,
        style=_prompt_style,
        completer=_SafeCompleter(
            ptpython.completer.PythonCompleter(
                lambda: globals, lambda: locals, lambda: False
            )
        ),
        complete_style=prompt_toolkit.shortcuts.CompleteStyle.MULTI_COLUMN,
        include_default_pygments_style=False,
        output=output,
    )
    try:
        # We launch this in a thread because `prompt_toolkit` calls into the current
        # asyncio loop. We don't want to do this -- we want to run our whole prompt
        # in blocking fashion -- so we need to run the whole thing with a new loop,
        # which necessarily means a new thread.
        text = _safe_run_in_thread(session.prompt)
    except (EOFError, KeyboardInterrupt):
        return state
    text_strip = text.strip()
    if text_strip == "" or text_strip.startswith("#"):
        return state
    width = shutil.get_terminal_size().columns
    try:
        value = eval(text, globals, locals)
        # We also include the formatting inside the `try`, as the object may have a
        # malformed `__repr__`.
        string = wl.pformat(value, width=width, short_arrays=short_arrays)
    except BaseException as e:
        string = "\n".join(_format_exception(e, short=False))
    else:
        if "\x1b" not in string:
            # If there's an escape code in there, then probably `string` has already
            # returned something with pretty formatting. Let's not try to second-guess
            # it.
            string = _syntax_highlight(string)
    _echo_first_line(string)  # `prompt` adds a newline.
    _echo_newline_end_command()
    return dataclasses.replace(state, print_history=history)


def _apply_to_frames_with_path(
    root_callstack: _Callstack, filepath: pathlib.Path, fn: Callable[[_Frame], None]
):
    agenda = [root_callstack]
    while len(agenda) > 0:
        callstack = agenda.pop()
        agenda.extend(callstack.down_callstacks)
        for frame in callstack.frames:
            if pathlib.Path(frame.f_code.co_filename).resolve() == filepath:
                fn(frame)


def _subprocess_edit(
    cmd: list[str],
    root_callstack: _Callstack,
    filepath: pathlib.Path,
    editor: str,
    depth: int,
    is_modified: bool,
) -> tuple[int, bool]:
    # Cache the source for all frames using this file, before we potentially modify the
    # file.
    _apply_to_frames_with_path(root_callstack, filepath, operator.methodcaller("cache"))
    _echo_first_line(_emph(str(filepath)))
    if is_modified:
        _echo_later_lines(
            _patdb_info(
                f"Warning: file `{filepath}` has been edited. This file does not "
                "necessarily correspond to the Python source that was actually ran, "
                "and the line at which the file is opened may be incorrect. Press any "
                "key to continue.",
                depth,
            )
        )
        click.getchar()
    filesource = filepath.read_bytes()
    try:
        result = subprocess.run(cmd)
    except Exception as e:
        # e.g. a PermissionError from `cmd` not existing.
        _echo_later_lines(_patdb_info(_format_exception(e, short=False), depth))
        _echo_later_lines(
            _patdb_info(
                f"Error in subprocess call. Is your `{editor}` set to a valid "
                "executable?",
                depth,
            )
        )
        return 0, False
    else:
        return result.returncode, filesource != filepath.read_bytes()


def _make_help(fn_keys):
    key_len = 0
    name_len = 0
    for fn, keys in fn_keys.items():
        key_len = max(key_len, sum(map(len, keys)) + len(keys) - 1)
        name_len = max(name_len, len(_fn_to_name(fn)))
    template = f"{{:{key_len}}}: {{:{name_len}}} - "
    name_width = len(template.format("", ""))
    doc_width = shutil.get_terminal_size().columns - name_width
    helpmsg = []
    for fn, keys in fn_keys.items():
        name = _fn_to_name(fn)
        doc = fn.__doc__.split("\n")[0].strip()
        if doc_width < 10:
            # In this case give up and just wrap all text.
            helpmsg.append(template.format("/".join(keys), name) + doc)
        else:
            doc_lines = textwrap.wrap(doc, doc_width)
            first_doc_line, *later_doc_lines = doc_lines
            helpmsg.append(template.format("/".join(keys), name) + first_doc_line)
            for line in later_doc_lines:
                helpmsg.append(" " * name_width + line)
    helpmsg = "\n".join(helpmsg)
    return helpmsg


class MultiprocessingSystemExit(Exception):
    pass


@contextlib.contextmanager
def _depth_context(depth: int):
    _config.depth = depth + 1
    try:
        yield
    finally:
        _config.depth = depth


#
# Commands
#


def _down_frame(state: _State) -> _State:
    """Move one frame down."""
    limit_msg = (
        "Already at bottommost frame. Press capital-J to move to the next callstack."
    )
    hidden_msg = (
        "Already at bottommost visible frame. Press capital-J to move to the next "
        "callstack. Note that {num_hidden} hidden frames were skipped."
    )
    frameless_msg = (
        "Callstack has no frames. Press capital-J to move to the next callstack."
    )
    move = _move_frame(
        state.location,
        skip_hidden=state.skip_hidden,
        down=True,
        include_current_location=False,
    )
    return _update_and_display_move(move, state, limit_msg, hidden_msg, frameless_msg)


def _up_frame(state: _State) -> _State:
    """Move one frame up."""
    limit_msg = (
        "Already at topmost frame. Press capital-K to move to the next callstack."
    )
    hidden_msg = (
        "Already at topmost visible frame. Press capital-K to move to the next "
        "callstack. Note that {num_hidden} hidden frames were skipped."
    )
    frameless_msg = (
        "Callstack has no frames. Press capital-K to move to the next callstack."
    )
    move = _move_frame(
        state.location,
        skip_hidden=state.skip_hidden,
        down=False,
        include_current_location=False,
    )
    return _update_and_display_move(move, state, limit_msg, hidden_msg, frameless_msg)


def _down_callstack(state: _State) -> _State:
    """Move one callstack down."""
    limit_msg = "Already at bottommost callstack."
    hidden_msg = (
        "Already at bottomost callstack. Note that {num_hidden} hidden frames were "
        "skipped."
    )
    frameless_msg = "<Callstack has no frames.>"
    move = _move_callstack(
        state.root_callstack,
        state.location,
        state.skip_hidden,
        down=True,
    )
    return _update_and_display_move(move, state, limit_msg, hidden_msg, frameless_msg)


def _up_callstack(state: _State) -> _State:
    """Move one callstack up."""
    limit_msg = "Already at topmost callstack."
    hidden_msg = (
        "Already at topmost callstack. Note that {num_hidden} hidden frames were "
        "skipped."
    )
    frameless_msg = "<Callstack has no frames.>"
    move = _move_callstack(
        state.root_callstack,
        state.location,
        state.skip_hidden,
        down=False,
    )
    return _update_and_display_move(move, state, limit_msg, hidden_msg, frameless_msg)


def _show_function(state: _State) -> _State:
    """Show the current function's source code and interactively set breakpoints."""
    frame = _current_frame(state.location)
    if isinstance(frame, str):
        _echo_first_line(frame)
        _echo_newline_end_command()
    else:
        if frame.function_source is None:
            _echo_first_line("<no source found>")
            _echo_newline_end_command()
        else:
            # i.e. we're on the bottom frame
            assert frame.local_filepath is not None
            _echo_first_line(_emph(str(frame.local_filepath)))
            jump_line_num, should_jump = _show_source(
                frame.function_source,
                frame.f_code.co_firstlineno,
                frame.line,
                state.depth,
            )
            if should_jump and jump_line_num != frame.line:
                # Note that we choose to modify the global trace hook here, *not* the
                # frame-local trace hook (i.e. setting `frame.f_trace = ...`, along with
                # a low-overhead global trace hook and `frame.f_trace_lines = True`).
                #
                # The reason is that we may have a closed-over function inside of our
                # current function, and if we select one of its lines then we'd actually
                # like to stop inside of that function instead.
                # That is, we're not necessarily going to be stopping somewhere inside
                # the current frame. So a single frame-local trace hook is not
                # appropriate.
                filepath = pathlib.Path(frame.f_code.co_filename).resolve()
                state = _install_trace(filepath, jump_line_num, state)
    return state


# Note that this command is deliberately not an interactive one with `s(t)ack`, in
# which we can scroll through the file or jump to where we are in it. For that there is
# `(e)dit`. (Honestly this command isn't super useful, just because `(e)dit` exists.)
def _show_file(state: _State) -> _State:
    """Show the current file's source code and interactively set breakpoints."""
    frame = _current_frame(state.location)
    if isinstance(frame, str):
        _echo_first_line(frame)
        _echo_newline_end_command()
    else:
        if frame.file_source is None:
            _echo_first_line("<no source found>")
            _echo_newline_end_command()
        else:
            assert frame.local_filepath is not None
            _echo_first_line(_emph(str(frame.local_filepath)))
            jump_line_num, should_jump = _show_source(
                frame.file_source, 1, frame.line, state.depth
            )
            assert jump_line_num is not None
            if should_jump and jump_line_num != frame.line:
                filepath = pathlib.Path(frame.f_code.co_filename).resolve()
                state = _install_trace(filepath, jump_line_num, state)
    return state


def _stack(state: _State) -> _State:
    """Show all frames in all callstacks and interactively scroll through them."""

    # Note that we have deliberately not added many other commands here!
    #
    # One of the design goals for `patdb` is that the scrollback in your window should
    # give a pretty effective history of all the things that you've (a) done, but more
    # importantly (b) _seen_, during your debugger session.
    #
    # Notably this "recording of history" is really the whole point of our choice of a
    # REPL-based interface -- as compared to a GUI-like interface (e.g. `pudb`).
    #
    # So in particular we do not do things like open a interpreter on the alternate
    # screen. This would result in changes of state that are not recorded here.
    #
    # What about e.g. opening an interpreter below, you ask? Well then, just press `c`
    # and then `i`!

    initial_stack_state = _StackState(
        state.location,
        state.skip_hidden,
        update_location=False,
        short_error=False,
        is_callstack_collapsed={
            callstack: callstack.collapse_default
            for callstack in _callstack_iter(
                state.root_callstack,
                None,
                lambda carry, _: carry,
                lambda callstack, _: callstack,
            )
        },
    )

    def _is_collapsed(stack_state: _StackState, callstack: _Callstack):
        return stack_state.is_callstack_collapsed[callstack]

    def _display(stack_state: _StackState) -> list[str]:
        return _window_text(
            _format_callstacks(
                state.root_callstack,
                stack_state.location,
                state.location,
                ft.partial(_is_collapsed, stack_state),
                stack_state.skip_hidden,
                stack_state.short_error,
            ),
            ellipsis="  │ ...",
        )

    def _stack_down_frame(stack_state: _StackState) -> tuple[_StackState, bool]:
        if _is_collapsed(stack_state, stack_state.location.callstack):
            return stack_state, False
        else:
            move = _move_frame(
                stack_state.location,
                skip_hidden=stack_state.skip_hidden,
                down=True,
                include_current_location=False,
            )
            return dataclasses.replace(stack_state, location=move.location), False

    def _stack_up_frame(stack_state: _StackState) -> tuple[_StackState, bool]:
        if _is_collapsed(stack_state, stack_state.location.callstack):
            return stack_state, False
        else:
            move = _move_frame(
                stack_state.location,
                skip_hidden=stack_state.skip_hidden,
                down=False,
                include_current_location=False,
            )
            return dataclasses.replace(stack_state, location=move.location), False

    def _stack_down_callstack(stack_state: _StackState) -> tuple[_StackState, bool]:
        move = _move_callstack(
            state.root_callstack,
            stack_state.location,
            stack_state.skip_hidden,
            down=True,
        )
        return dataclasses.replace(stack_state, location=move.location), False

    def _stack_up_callstack(stack_state: _StackState) -> tuple[_StackState, bool]:
        move = _move_callstack(
            state.root_callstack,
            stack_state.location,
            stack_state.skip_hidden,
            down=False,
        )
        return dataclasses.replace(stack_state, location=move.location), False

    def _stack_visibility(stack_state: _StackState) -> tuple[_StackState, bool]:
        return dataclasses.replace(
            stack_state, skip_hidden=not stack_state.skip_hidden
        ), False

    def _stack_error(stack_state: _StackState) -> tuple[_StackState, bool]:
        return dataclasses.replace(
            stack_state, short_error=not stack_state.short_error
        ), False

    def _stack_collapse_single(stack_state: _StackState) -> tuple[_StackState, bool]:
        is_callstack_collapsed = stack_state.is_callstack_collapsed.copy()
        is_callstack_collapsed[stack_state.location.callstack] = not _is_collapsed(
            stack_state, stack_state.location.callstack
        )
        return dataclasses.replace(
            stack_state, is_callstack_collapsed=is_callstack_collapsed
        ), False

    def _stack_collapse_all(stack_state: _StackState) -> tuple[_StackState, bool]:
        value = not all(stack_state.is_callstack_collapsed.values())
        is_callstack_collapsed = stack_state.is_callstack_collapsed.copy()
        for key in is_callstack_collapsed.keys():
            is_callstack_collapsed[key] = value
        return dataclasses.replace(
            stack_state, is_callstack_collapsed=is_callstack_collapsed
        ), False

    def _stack_select(stack_state: _StackState) -> tuple[_StackState, bool]:
        return dataclasses.replace(stack_state, update_location=True), True

    def _stack_leave(stack_state: _StackState) -> tuple[_StackState, bool]:
        return stack_state, True

    key_mapping: dict = {
        _stack_down_frame: (_config.key_stack_down_frame, None),
        _stack_up_frame: (_config.key_stack_up_frame, None),
        _stack_down_callstack: (_config.key_stack_down_callstack, None),
        _stack_up_callstack: (_config.key_stack_up_callstack, "to scroll"),
        "left": (_config.key_stack_left, None),
        "right": (_config.key_stack_right, "to move view left/right"),
        _stack_visibility: (_config.key_stack_visibility, "to show/hide hidden frames"),
        _stack_error: (_config.key_stack_error, "to show/hide error messages"),
        _stack_collapse_single: (
            _config.key_stack_collapse_single,
            "to show/hide a callstack",
        ),
        _stack_collapse_all: (
            _config.key_stack_collapse_all,
            "to show/hide every callstack",
        ),
        _stack_select: (_config.key_stack_select, "to switch to a frame"),
        _stack_leave: (_config.key_stack_leave, "to leave stack mode"),
    }
    final_stack_state = _basic_app(
        initial_stack_state, _display, key_mapping, state.depth
    )
    if final_stack_state.update_location:
        state = dataclasses.replace(
            state,
            location=final_stack_state.location,
            skip_hidden=final_stack_state.skip_hidden,
        )
    frame = _current_frame(final_stack_state.location)
    if isinstance(frame, str):
        msg = frame
        source_line = None
    else:
        msg = _format_frame(frame)
        source_line = _show_line(frame)
    _echo_first_line(msg)  # `app.run()` adds a newline.
    if source_line is not None:
        _echo_later_lines(source_line)
    _echo_newline_end_command()
    return state


def _print(state: _State) -> _State:
    """Pretty-prints the value of an expression.

    Printing a variable is such a common thing to do that we break our usual "minimal
    interface" rule, and we do offer a special command for this. (As opposed to opening
    an interpreter and printing the value there.)
    """
    return _pprint(state, short_arrays=True)


def _print_long_arrays(state: _State) -> _State:
    """Pretty-prints the value of an expression, without summarising arrays."""
    return _pprint(state, short_arrays=False)


def _edit(state: _State) -> _State:
    """Open the current function in your $EDITOR.

    This will be called as `$EDITOR <filename>`.

    Alternatively if you have a `$PATDB_EDITOR` environment variable set, then this will
    be called with `$PATDB_EDITOR <filename> <linenumber>`, which you can use to
    configure your editor to open at a specific line number.
    """
    frame = _current_frame(state.location)
    if isinstance(frame, str):
        _echo_first_line(frame)
        _echo_newline_end_command()
        return state
    interpreter_filename = frame.f_code.co_filename
    local_filepath = frame.local_filepath
    if local_filepath is None:
        _echo_later_lines(
            _patdb_info(
                f"No source available for filename `{interpreter_filename}`.",
                state.depth,
            )
        )
        _echo_newline_end_command()
        return state
    linenumber = str(frame.line)
    line_editor = _config.line_editor
    is_modified = local_filepath in state.modified_files
    if line_editor is None or line_editor == "":
        editor = _config.editor
        if editor is None or editor == "":
            _echo_later_lines(
                _patdb_info(
                    "Neither `EDITOR` nor `PATDB_EDITOR` is configured.", state.depth
                )
            )
            returncode = 0
            modified = False
        else:
            returncode, modified = _subprocess_edit(
                [editor, str(local_filepath)],
                state.root_callstack,
                local_filepath,
                "EDITOR",
                state.depth,
                is_modified,
            )
    else:
        returncode, modified = _subprocess_edit(
            [line_editor, str(local_filepath), linenumber],
            state.root_callstack,
            local_filepath,
            "PATDB_EDITOR",
            state.depth,
            is_modified,
        )
    if returncode != 0:
        _echo_later_lines(
            _patdb_info(f"Error with returncode {returncode}", state.depth)
        )
    _echo_newline_end_command()
    if modified:
        modified_files = frozenset({*state.modified_files, local_filepath})
        state = dataclasses.replace(state, modified_files=modified_files)
    return state


def _interpret(state: _State) -> _State:
    """Open a Python interpreter in the current frame."""
    frame = _current_frame(state.location)
    if isinstance(frame, str):
        _echo_first_line(frame)
        _echo_newline_end_command()
        return state
    # Adjust our prompts based on how nested our interpreters and debuggers are.
    globals, locals = _make_namespaces(state)
    sentinel = object()
    last_e = {
        last_e_name: getattr(sys, last_e_name, sentinel)
        for last_e_name in ("last_type", "last_value", "last_traceback", "last_exc")
    }
    try:
        _echo_later_lines("")
        with _disable_logging():
            ptpython.repl.embed(
                globals,
                locals,
                configure=_ptpython_configure,
                history_filename=str(_patdb_history_file),
            )
    except SystemExit:
        pass
    finally:
        for last_e_name, last_e_value in last_e.items():
            if last_e_value is sentinel:
                if hasattr(sys, last_e_name):
                    delattr(sys, last_e_name)
            else:
                setattr(sys, last_e_name, last_e_value)
    # We already have a spurious newline from the interpreter
    # _echo_newline_end_command()
    return state


def _visibility(state: _State) -> _State:
    """Toggles skipping hidden frames when moving frames or callstacks."""
    state = dataclasses.replace(state, skip_hidden=not state.skip_hidden)
    if state.skip_hidden:
        _echo_first_line("Now skipping hidden frames.")
    else:
        _echo_first_line("Now displaying hidden frames.")
    _echo_newline_end_command()
    return state


def _continue(state: _State) -> _State:
    """Close the debugger and continue the program."""
    _echo_first_line("Continuing.")
    _echo_newline_end_command()
    return dataclasses.replace(state, done=True)


def _quit(state: _State) -> NoReturn:
    """Quit the whole Python program."""
    del state
    # When using `pytest` -> `breakpoint()` -> `(q)uit`, it shows the visible stack
    # frames in between.
    __tracebackhide__ = True

    _echo_first_line("Quitting.")
    _echo_newline_end_command()
    if multiprocessing.parent_process() is None:
        sys.exit()
    else:
        # For some reason multiprocessing only handles Exceptions, but not
        # BaseExceptions, gracefully. If we just raise a `SystemExit` (from `sys.exit`)
        # then multiprocessing in the parent process will just hang.
        raise MultiprocessingSystemExit


def _help(state: _State) -> _State:
    """Display a list of all debugger commands."""
    _echo_later_lines(state.helpmsg())
    _echo_newline_end_command()
    return state


#
# Entry point
#


# Called manually by a user as `breakpoint()` (or just directly via `patdb.debug()`,
# same thing really).
@overload
def debug(*, stacklevel: int = 1): ...


# Called manually by a user on their favourite exception, (E.g. we do this ourselves in
# `__main__.py`.)
@overload
def debug(e: BaseException, /): ...


# Called manually by a user on their favourite traceback.
@overload
def debug(tb: types.TracebackType, /): ...


# Called manually by a user on their favourite frame.
@overload
def debug(tb: types.FrameType, /): ...


# Called automatically by Python in `sys.excepthook()`
@overload
def debug(type, value, traceback, /): ...


def debug(*args, stacklevel: int = 1):
    """Starts the PatDB debugger. This is the main entry point into the library.

    Usage is any one of the following.

    1. This runs the debugger at the current location:

        ```
        debug()
        ```

        If an exception has previously been raised to the top level (available at
        `sys.last_value`) then this will open a post-mortem debugger to navigate the
        stack of this exception. This is useful when on the Python REPL.

        Otherwise, the current `inspect.stack()` is used, so that `debug` instead
        provides a breakpoint. This is useful to insert inside of source code.

    2. This open a breakpoint this many stack frames above (useful if you're wrapping
        `patdb.debug` with your own functionality):

        ```
        debug(stacklevel=<some integer>)
        ```

    3. Given `some_exception` of type `BaseException`, then this allows you to
        investigate its traceback:

        ```
        debug(some_exception)
        ```

    4. Given `some_traceback` of type `types.TracebackType`, then this allows you to
        investigate the traceback:

        ```
        debug(some_traceback)
        ```

    5. This can be used as your default `breakpoint()` by setting
        `PYTHONBREAKPOINT=patdb.debug`, and as your exception hook by setting
        `sys.excepthook=patdb.debug`.
    """
    # When using `pytest` -> `breakpoint()` -> `(q)uit`, it shows the visible stack
    # frames in between.
    __tracebackhide__ = True

    # Ensure that we work in multithreaded contexts.
    #
    # Also disable breakpoints during initial set-up of `_debug`. We'll re-enable this
    # when we enter the patdb REPL.
    # This is to avoid infinite loops, in case we should happen to encounter a
    # breakpoint during initial set-up.
    #
    # These are done as contexts here rather than decorators on `_debug`, so that the
    # decorator-as-context-manager frame does not appear when (q)uitting out of pytest.
    with _one_breakpoint_at_a_time():
        with _override_breakpointhook(lambda *a, **kw: None), _disable_pytest_capture():
            done_cell = _debug(*args, stacklevel=stacklevel)
    gc.collect()
    # We fill in `done_cell` only after the entirety of the `_debug` frame is gone and
    # the gc has been ran. This ensures that we will not trigger `_next_call_trace`
    # during e.g. weakref finalisation.
    done_cell[0] = True


if sys.platform == "darwin" or sys.platform.startswith("linux"):
    (pathlib.Path.home() / ".local" / "patdb").mkdir(parents=True, exist_ok=True)

    # I had a long painful time trying to get locking working with multiprocessing, and
    # did not succeed. At least on MacOS then it seems like `multiprocessing.Lock` only
    # works if either (a) you use the `fork` method, or (b) you pass the lock to the
    # process as an argument. (Noting that the default method on MacOS is `spawn`, which
    # only copies across what is needed for the subprocess.)
    #
    # As such getting this working seems quite difficult! Especially as `patdb` probably
    # isn't even imported into the parent process, but will be dynamically imported into
    # the child process once a breakpoint is hit.
    #
    # So... we're using the filesystem instead. Not a great solution but it does work.
    # In non-multiprocessing contexts the overhead should be negligible, just the cost
    # of creating/destroying the file.
    #
    # We gate this whole block on being on Unix, so that `os.getpgrp()` will work. I
    # don't currently have a Windows/etc. machine to check other systems for what their
    # equivalents should be.
    class _Lock:
        def __init__(self, name: Any):
            # Include a normal threading lock so that multiple threads can lock without
            # CPU overhead (as the filesystem component of the locking uses a busy loop
            # below, not cheap!)
            self.lock = threading.Lock()
            self.filepath = (
                pathlib.Path.home() / ".local" / "patdb" / f"lock-{name}-{os.getpgrp()}"
            )

        def __enter__(self):
            self.lock.__enter__()
            while True:
                while self.filepath.exists():
                    time.sleep(0.1)
                try:
                    self.filepath.touch(exist_ok=False)
                except FileExistsError:
                    continue  # race condition between `filepath.exists()` and now.
                break  # lock acquired

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.filepath.unlink()
            return self.lock.__exit__(exc_type, exc_val, exc_tb)
else:
    _Lock = lambda name: threading.Lock()


_metalock = _Lock(name="meta")
_locks = {}


# We parameterize our locks by depth. This is basically an improvement over using an
# RLock, in that nested calls to `debug` will work regardless of whether we create them
# in the same thread or not.
@contextlib.contextmanager
def _one_breakpoint_at_a_time():
    with _metalock:
        try:
            lock = _locks[_config.depth]
        except KeyError:
            lock = _locks[_config.depth] = _Lock(_config.depth)
    with lock:
        yield


_pytest_pluginmanager = None


# This (a) gives compatibility with the `capfd` fixture, and (b) avoids the need to pass
# the `-s` flag to pytest.
@contextlib.contextmanager
def _disable_pytest_capture():
    if _pytest_pluginmanager is not None:
        capman = _pytest_pluginmanager.getplugin("capturemanager")
        if capman:
            capman.suspend(in_=True)
            try:
                yield
            finally:
                capman.resume()
        else:
            yield
    else:
        yield


@contextlib.contextmanager
def _multiprocessing_stdin():
    try:
        stdin_fileno = sys.stdin.fileno()
    except Exception:
        # Not all file-likes have a fileno, e.g.
        # https://stackoverflow.com/questions/44123116/in-python-error-on-sys-stdin-fileno
        yield
    else:
        if (
            not os.isatty(stdin_fileno)
            and os.isatty(0)
            and multiprocessing.parent_process() is not None
        ):
            # We're in a subprocess created by `multiprocessing`. By default we don't
            # get a stdin. Time to steal it from our parent process!
            old_stdin_fileno = os.dup(stdin_fileno)
            os.dup2(0, stdin_fileno)
            try:
                yield
            finally:
                os.dup2(old_stdin_fileno, stdin_fileno)
        else:
            yield


def _debug(*args, stacklevel: int) -> list[bool]:
    # When using `pytest` -> `breakpoint()` -> `(q)uit`, it shows the visible stack
    # frames in between.
    __tracebackhide__ = True

    #
    # Step 1: figure out how we're being called, and get the callstacks.
    #

    e: None | BaseException | types.TracebackType | types.FrameType
    if len(args) == 0:
        # `debug()`
        # i.e. when `sys.breakpointhook = debug`
        e = None
    elif len(args) == 1:
        # `debug(some_exception)`, `debug(some_traceback)`, `debug(some_frame)`
        # i.e. when called manually
        [e] = args
    elif len(args) == 3:
        # `debug(some_exception_type, some_exception, some_traceback)`
        # i.e. when `sys.excepthook = debug`
        _, e, _ = args
    else:
        raise TypeError(
            "Usage is either `patdb.debug()` or `patdb.debug(some_exception)` or "
            "`patdb.debug(some_traceback)`."
        )
    if e is not None and stacklevel != 1:
        raise TypeError("Cannot pass `stacklevel` alongside an exception or traceback.")

    if e is None:
        # Called as an explicit `breakpoint()`.
        # Check `sys.last_exc` so that the same function also performs post-mortem when
        # on the REPL.
        for name in ("last_exc", "last_value"):
            try:
                e = getattr(sys, name)
            except AttributeError:
                pass
    if isinstance(e, BaseException):
        # Called as either:
        # - an explicit `breakpoint()` for post-mortem.
        # - an explicit `patdb.debug(some_exception)`
        # - an implicit `sys.excepthook`.
        if e.__traceback__ is None:
            # Don't trigger on top-level SyntaxErrors/KeyboardInterrupts/etc.
            return [False]
        if isinstance(e, bdb.BdbQuit):
            # If someone has mix-and-matched with bdb or pdb then don't raise on those.
            return [False]
        if isinstance(e, SystemExit):
            # We definitely don't to intercept this one!
            return [False]
        root_callstack = _get_callstacks_from_error(
            e,
            up_callstack=None,
            kinds=frozenset([_CallstackKind.toplevel]),
            collapse_default=False,
        )
        find_visible = True
    else:
        if e is None:
            # Called as an explicit `breakpoint()`.
            frame_infos = tuple(
                frame_info for frame_info in inspect.stack()[1 + stacklevel :][::-1]
            )
            frame_hidden = False
            frames = []
            for frame_info in frame_infos:
                frame_hidden = _is_frame_hidden(frame_info.frame, frame_hidden)
                frames.append(
                    _Frame(frame_info.frame, frame_info.frame.f_lineno, frame_hidden)
                )
            frames = tuple(frames)
            find_visible = False
        elif isinstance(e, types.FrameType):
            _frames: list[types.FrameType] = []
            while e is not None:
                _frames.append(e)
                e = e.f_back
            frames = []
            frame_hidden = False
            for frame in reversed(_frames):
                frame_hidden = _is_frame_hidden(frame, frame_hidden)
                frames.append(_Frame(frame, frame.f_lineno, frame_hidden))
            del _frames
            frames = tuple(frames)
            find_visible = False
        elif isinstance(e, types.TracebackType):
            # Called as an explicit `patdb.debug(some_traceback)`.
            frames = []
            frame_hidden = False
            while e is not None:
                frame_hidden = _is_frame_hidden(e.tb_frame, frame_hidden)
                frames.append(_Frame(e.tb_frame, e.tb_lineno, frame_hidden))
                e = e.tb_next
            frames = tuple(frames)
            find_visible = True
        else:
            raise TypeError(f"Cannot apply `patdb.debug` to object of type {type(e)}")
        root_callstack = _Callstack(
            _up_callstack=None,
            down_callstacks=(),
            frames=frames,
            kinds=frozenset([_CallstackKind.toplevel]),
            exception=None,
            collapse_default=False,
        )
        del frames

    #
    # Step 2: build our keybindings
    #
    key_mapping = {
        _down_frame: _config.key_down_frame,
        _up_frame: _config.key_up_frame,
        _down_callstack: _config.key_down_callstack,
        _up_callstack: _config.key_up_callstack,
        _show_function: _config.key_show_function,
        _show_file: _config.key_show_file,
        _stack: _config.key_stack,
        _print: _config.key_print,
        _print_long_arrays: _config.key_print_long_arrays,
        _edit: _config.key_edit,
        _interpret: _config.key_interpret,
        _visibility: _config.key_visibility,
        _continue: _config.key_continue,
        _quit: _config.key_quit,
        _help: _config.key_help,
    }
    depth = _config.depth
    key_bindings_, fn_keys, errors = _make_key_bindings(key_mapping, depth)
    if len(errors) != 0:
        for error in errors:
            _echo_first_line(error)
            click.echo("")
    key_bindings = prompt_toolkit.key_binding.KeyBindings()
    detected_fn = None
    detected_keys = None
    for binding in key_bindings_.bindings:

        @ft.wraps(binding.handler)
        def fn_wrapper(event, fn=binding.handler, keys=binding.keys):
            nonlocal detected_fn
            nonlocal detected_keys
            detected_fn = fn
            detected_keys = ",".join(
                k.value if isinstance(k, prompt_toolkit.keys.Keys) else k for k in keys
            )
            event.app.exit()

        key_bindings.add(*binding.keys)(fn_wrapper)
    del key_bindings_
    # We provide this as a callback as terminal width may change after the debugger has
    # started.
    helpmsg = lambda fn_keys=fn_keys: _make_help(fn_keys)

    #
    # Step 3: make the initial state of our REPL.
    #
    if len(root_callstack.frames) == 0:
        # Is this branch even possible?
        frame_idx = None
    else:
        # Start at the same spot as `pdb`, at the bottom of the topmost callstack.
        # I experimented with starting at the bottommost callstack instead, but the
        # difference didn't seem that important, and consistency with `pdb` here might
        # offer a better UX?
        frame_idx = len(root_callstack.frames) - 1
        if find_visible:
            bottom_frame_idx = frame_idx
            while True:
                if root_callstack.frames[frame_idx].is_hidden:
                    if frame_idx == 0:
                        # Could not find any unhidden frames. Default to the bottom one.
                        frame_idx = bottom_frame_idx
                        break
                    else:
                        frame_idx -= 1
                else:
                    # Found our bottommost unhidden frame.
                    break
    state = _State(
        # Replaceable
        done=False,
        skip_hidden=True,
        location=_Location(root_callstack, frame_idx),
        done_cell=[False],
        # Not replaceable
        print_history=prompt_toolkit.history.InMemoryHistory(),
        helpmsg=helpmsg,
        root_callstack=root_callstack,
        depth=depth,
        modified_files=frozenset(),
    )

    #
    # Step 5: print header information
    #
    frame_info = _current_frame(state.location)
    if isinstance(frame_info, str):
        frame_info = frame_info
    else:
        frame_info = _format_frame(frame_info)
    click.echo(frame_info)
    if e is not None:
        click.echo("\n".join(_format_exception(e, short=False)))
    if not isinstance(frame_info, str):
        source_line = _show_line(frame_info)
        if source_line is not None:
            click.secho(source_line, reset=True)
    try:
        helpkeys = fn_keys[_help]
    except KeyError:
        # It could occur that this someone has rebound away the help key, or had a
        # keybinding clash.
        pass
    else:
        helpkeys = "/".join(helpkeys)
        click.echo(
            _patdb_info(f"Press {helpkeys} for a list of all commands.", state.depth)
        )
        del helpkeys
    del fn_keys

    #
    # Step 6: run the REPL!
    #

    prompt = _patdb_prompt(state.depth)

    # `prompt_toolkit` has its own hook that it will set sometimes.
    # In some multithreaded programs it seems that it is possible (somehow?) for that
    # hook to be the current one whilst another thread triggers the breakpoint.
    #
    # We only set this here in case we enter a `breakpoint()` during the initial set-up
    # of this function.
    with (
        _override_breakpointhook(debug),
        _depth_context(state.depth),
        _multiprocessing_stdin(),
    ):
        container = prompt_toolkit.layout.containers.Window(
            content=prompt_toolkit.layout.controls.DummyControl()
        )
        layout = prompt_toolkit.layout.Layout(container)
        output = prompt_toolkit.output.create_output()
        if hasattr(output, "enable_cpr"):
            output.enable_cpr = False  # pyright: ignore[reportAttributeAccessIssue]
        app = prompt_toolkit.Application(
            full_screen=False,
            layout=layout,
            key_bindings=key_bindings,
            include_default_pygments_style=False,
            output=output,
        )

        while not state.done:
            click.echo(prompt, nl=False)
            try:
                _safe_run_in_thread(app.run)
            except EOFError as e:
                raise RuntimeError(
                    "Could not start the debugger, probably because it could not "
                    "connect to `sys.{stdin,stdout}`.\n"
                    "If you are using `breakpoint()` or `patdb.debug()` from "
                    "within `pytest`, then this can be fixed by adding the `-s` "
                    "flag.\n"
                    "If you are using `patdb` from within an environment like "
                    "Jupyter or Marimo, then unfortunately these are not "
                    "compatible with `patdb`, as these environments do not support "
                    "terminal emulation capabilities."
                ) from e
            assert detected_fn is not None
            assert detected_keys is not None
            # Convention on \n:
            #
            # We split up the response of each command into the "first line"
            # (appears on the same line as the prompt and the detected keys) and the
            # "later lines" (appears on subsequent lines).
            # Every command should call the `_echo_first_line` or
            # `_echo_later_lines` functions to do the right thing.
            # Every command should end with a call to `_echo_newline_end_command` to
            # insert the newline for the next prompt.
            #
            # We let each command handle doing this, as someone of them call out to
            # other processes, which don't always do consistent things. This offers
            # some wiggle room as an escape hatch. (E.g. `interact` leaves off
            # `_echo_newline_end_command`).
            click.echo(f"{detected_keys}: ", nl=False)
            state = detected_fn(state)

    # We have a variable here that we explicitly hang on to for the lifetime of `debug`.
    # This `del` is used as a static assertion (for pyright) that it has *not* been
    # `del`'d at any previous point.
    #
    # Our callstacks are laid out as a tree, with nodes holding strong references to
    # their children but weak references to their parents. So we need to hold on to a
    # reference to the root to be sure that they all stay in memory until `debug` is
    # done.
    #
    # The reason for the use of these weakrefs is to avoid creating cyclic garbage,
    # with our callstacks holding strong references to each other. Python will clean
    # that up but it's less efficient.
    # Notably our callstacks hold references to frames hold references to *every* local
    # variable throughout our program, so doing the right thing here seems like it might
    # matter?
    # It's probably not that important, but doing the right thing here isn't too tricky,
    # so we do it anyway.
    del root_callstack
    return state.done_cell
