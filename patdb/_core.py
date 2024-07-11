import bdb
import builtins
import collections as co
import dataclasses
import enum
import functools as ft
import importlib.machinery
import inspect
import os
import pathlib
import pprint
import re
import shutil
import subprocess
import sys
import textwrap
import threading
import traceback
import types
import weakref
from collections.abc import Callable, Iterable, Iterator
from typing import Any, NoReturn, Optional, overload, TypeVar, Union
from typing_extensions import Self, TypeGuard

import click
import prompt_toolkit
import prompt_toolkit.completion
import prompt_toolkit.cursor_shapes
import prompt_toolkit.document
import prompt_toolkit.formatted_text
import prompt_toolkit.history
import prompt_toolkit.input.ansi_escape_sequences
import prompt_toolkit.key_binding
import prompt_toolkit.keys
import prompt_toolkit.layout
import prompt_toolkit.layout.containers
import prompt_toolkit.layout.controls
import prompt_toolkit.lexers
import prompt_toolkit.output.vt100
import prompt_toolkit.shortcuts
import prompt_toolkit.styles.pygments
import prompt_toolkit.widgets
import ptpython
import ptpython.completer
import ptpython.prompt_style
import pygments
import pygments.formatters
import pygments.lexers
import pygments.styles
import pygments.token


#
# Configuration
#


class _FormatConfig:
    @ft.cached_property
    def code_style(self) -> str:
        return os.getenv("PATDB_CODE_STYLE", "solarized-dark")

    #
    # These default colours are carefully chosen to be visible on both light and dark
    # terminal backgrounds.
    #

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


class _KeyConfig:
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
    def key_stack_select(self) -> str:
        return os.getenv("PATDB_KEY_STACK_SELECT", "t")

    @ft.cached_property
    def key_stack_leave(self) -> str:
        return os.getenv("PATDB_KEY_STACK_LEAVE", "q")

    @ft.cached_property
    def key_print(self) -> str:
        return os.getenv("PATDB_KEY_PRINT", "p")

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
    def key_toggle_error(self) -> str:
        return os.getenv("PATDB_KEY_TOGGLE_ERROR", "r")

    @ft.cached_property
    def key_toggle_collapse_single(self) -> str:
        return os.getenv("PATDB_KEY_TOGGLE_COLLAPSE_SINGLE", "o")

    @ft.cached_property
    def key_toggle_collapse_all(self) -> str:
        return os.getenv("PATDB_KEY_TOGGLE_COLLAPSE_ALL", "O")

    @ft.cached_property
    def key_continue(self) -> str:
        return os.getenv("PATDB_KEY_CONTINUE", "c")

    @ft.cached_property
    def key_quit(self) -> str:
        return os.getenv("PATDB_KEY_QUIT", "q")

    @ft.cached_property
    def key_help(self) -> str:
        return os.getenv("PATDB_KEY_HELP", "?")


class _MiscConfig:
    # Uncached, it may change as we nest.
    @property
    def depth(self) -> Optional[int]:
        out = os.getenv("PATDB_DEPTH", None)
        if out is None:
            return None
        else:
            return int(out)

    @depth.setter
    def depth(self, value: int):
        os.environ["PATDB_DEPTH"] = str(value)

    @depth.deleter
    def depth(self):
        del os.environ["PATDB_DEPTH"]

    @ft.cached_property
    def line_editor(self) -> Optional[str]:
        return os.getenv("PATDB_EDITOR", None)

    @ft.cached_property
    def editor(self) -> Optional[str]:
        return os.getenv("EDITOR", None)

    @ft.cached_property
    def colorfgbg(self) -> Optional[str]:
        return os.getenv("COLORFGBG", None)

    @ft.cached_property
    def ptpython_config_home(self) -> Optional[str]:
        return os.getenv("PTPYTHON_CONFIG_HOME", None)


def _hex_to_rgb(x: str) -> Optional[tuple[int, int, int]]:
    x = _keep_fg_only(x)
    if x == "":
        return None
    else:
        x = x.removeprefix("#")
        return int(x[:2], base=16), int(x[2:4], base=16), int(x[4:], base=16)


class _Config(_FormatConfig, _KeyConfig, _MiscConfig):
    pass


_config = _Config()


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
    except ValueError:
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
    click.echo("")


#
# Managing callstacks and frames
#


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

    @property
    def f_code(self):
        return self._frame.f_code

    @property
    def f_locals(self):
        return self._frame.f_locals

    @property
    def f_globals(self):
        return self._frame.f_globals

    def getsource(self):
        return inspect.getsource(self._frame)

    def getsourcelines(self):
        return inspect.getsourcelines(self._frame)

    def getsourcefile(self):
        return inspect.getsourcefile(self._frame)


class _CallstackKind(enum.Enum):
    # Order corresponds to the order printed out when we have multiple kinds.
    toplevel = 0
    group = 1
    cause = 2
    context = 3
    suppressed_context = 4


@dataclasses.dataclass(frozen=True, eq=False)
class _Callstack:
    _up_callstack: Optional[weakref.ref[Self]]
    down_callstacks: tuple[Self, ...]
    frames: tuple[_Frame, ...]
    kinds: frozenset[_CallstackKind]
    exception: Optional[BaseException]
    collapse_default: bool

    def __post_init__(self):
        assert len(self.kinds) != 0

    @property
    def up_callstack(self) -> Optional[Self]:
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


def _get_callstacks_from_error(
    exception: BaseException,
    up_callstack: Optional[_Callstack],
    kinds: frozenset[_CallstackKind],
    collapse_default: bool,
) -> _Callstack:
    tb = exception.__traceback__
    frames: list[_Frame] = []
    while tb is not None:
        frames.append(_Frame(tb.tb_frame, tb.tb_lineno))
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
    frame_idx: Optional[int]

    def __post_init__(self):
        if len(self.callstack.frames) == 0:
            assert self.frame_idx is None
        else:
            assert self.frame_idx is not None
            assert 0 <= self.frame_idx < len(self.callstack.frames)


def _current_frame(location: _Location) -> Union[str, _Frame]:
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
            if skip_hidden and _is_frame_hidden(frame):
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
    print_history: prompt_toolkit.history.InMemoryHistory
    helpmsg: str
    root_callstack: _Callstack


def _is_frame_frozen(frame: _Frame) -> bool:
    # Skip the noise from `runpy`, in particular as used in our `__main__.py`.
    return frame.f_globals.get("__loader__", None) is importlib.machinery.FrozenImporter


def _is_frame_nameless(frame: _Frame) -> bool:
    # Skip the noise from JAX's JaxStackTraceBeforeTransformation causes, which are
    # highly sus. They're placed out-of-order in the __cause__/__context__ stack because
    # default `pdb` does a terrible job and orders chained stack frames
    # nonchronologically, i.e. the exact problem that `patdb` originally set out to fix.
    # Anyway, this often makes them the root traceback despite not being the root cause,
    # so we want to skip them by default.
    return "__name__" not in frame.f_globals


def _is_frame_angled(frame: _Frame) -> bool:
    # In particular `ptpython`'s REPL has the filename listed as `<stdin>`, but (unlike
    # the normal Python REPL) does not set `__name__`. So we need to carve out an
    # exception from `_is_frame_nameless`.
    return frame.f_code.co_filename.startswith("<")


def is_frame_pytest(frame: _Frame) -> bool:
    # Skip all of the noise in pytest when using the `--patdb` flag.
    name = frame.f_globals.get("__name__", "")
    for module in ("pytest", "_pytest", "pluggy"):
        if name == module or name.startswith(f"{module}."):
            return True
    return False


def _is_frame_hidden(frame: _Frame) -> bool:
    return (
        frame.f_locals.get("__tracebackhide__", False)
        or _is_frame_frozen(frame)
        or (_is_frame_nameless(frame) and not _is_frame_angled(frame))
        or is_frame_pytest(frame)
    )


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


def _ptpython_configure(repl: ptpython.repl.PythonRepl):
    config = _config.ptpython_config_home
    if config is not None and os.path.exists(config):
        ptpython.repl.run_config(repl, config)
    if _config.depth is not None:
        for k, v in list(repl.all_prompt_styles.items()):
            repl.all_prompt_styles[k] = _IndentPrompt(_config.depth, v)
    repl.completer = _SafeCompleter(repl.completer)


_patdb_history_file = pathlib.Path.home() / ".cache" / "patdb" / "history"
_patdb_history_file.parent.mkdir(parents=True, exist_ok=True)
_patdb_history_file.touch()


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
        completions = iter(self.completer.get_completions(document, complete_event))
        while True:
            try:
                completion = next(completions)
            except StopIteration:
                break
            except Exception:
                pass
            else:
                yield completion


#
# Implementations for the REPL and its commands
#


# Note that we must not cache the result of this function, as else nested `patdb`
# instances will not pick up on the correct depth.
def _patdb_prompt() -> str:
    """The REPL command prompt."""
    depth = _config.depth
    if depth is None:
        depth = ""
    return click.style(f"patdb{depth}> ", fg=_config.prompt_colour)


def _patdb_info(x: str):
    """Used to display information about `patdb` itself, e.g. command hints.

    Should NOT be used to display information about the current session state, e.g.
    stack locations.
    """
    depth = _config.depth
    if depth is None:
        depth = ""
    return click.style(f"patdb{depth}: " + x, fg=_config.info_colour)


def _make_key_bindings(key_mapping: dict[Callable, str]):
    errors = []
    key_bindings = prompt_toolkit.key_binding.KeyBindings()
    fn_keys = {}
    keys_fn = {}
    for fn, keys in key_mapping.items():
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
                        f"Keeping just `{_fn_to_name(existing_fn)}`."
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
                        f"Misconfigured `patdb`. `{key}` is not a valid command."
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


def _format_frame(frame: _Frame, prefix: Optional[str] = None) -> str:
    file = frame.f_code.co_filename
    if file.startswith("/"):
        if prefix is not None:
            file = file.removeprefix(prefix)
    elif not file.startswith("<"):
        file = "./" + file
    # co_qualname is Python 3.11+
    name = getattr(frame.f_code, "co_qualname", "co_name")
    current_line = str(frame.line)
    function_line = str(frame.f_code.co_firstlineno)
    return (
        f"File {_emph(file)}, at {_emph(name)} from {_emph(function_line)}, "
        f"line {_emph(current_line)}"
    )


def _format_callstack(
    callstack: _Callstack,
    interactive_location: Optional[_Location],
    current_location: Optional[_Location],
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
    is_collapsed_callstack = is_collapsed(callstack)
    if len(callstack.frames) == 0:
        is_hidden_callstack = False
    else:
        is_hidden_callstack = True
    for j, frame in enumerate(callstack.frames):
        is_hidden_frame = is_collapsed_callstack or _is_frame_hidden(frame)
        if is_hidden_frame:
            num_hidden_frames += 1
        is_current_frame = is_current_callstack and j == current_frame_idx
        is_interactive_frame = is_interactive_callstack and j == interactive_frame_idx
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
            if is_hidden_frame:
                hidden_left = "("
                hidden_right = ")"
            else:
                hidden_left = " "
                hidden_right = " "
            yield (
                f"{frame_arrow}{indent}{hidden_left}{frame_str}{hidden_right}",
                is_interactive_frame,
            )
        if callstack.exception is not None:
            e_lines = _format_exception(callstack.exception, short)
            for line in e_lines[:-1]:
                yield f"  {indent} {line}", False
            if len(callstack.down_callstacks) == 0:
                final_indent = last_indent
            else:
                final_indent = indent
            yield f"  {final_indent} {e_lines[-1]}", False


def _format_callstack_windowed(
    root_callstack: _Callstack,
    interactive_location: _Location,
    current_location: _Location,
    is_collapsed: Callable[[_Callstack], bool],
    skip_hidden: bool,
    short: bool,
) -> list[prompt_toolkit.formatted_text.OneStyleAndTextTuple]:
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
    its_the_final_countdown: Optional[int] = None

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

    first_line = None
    for callstack_info_iterable in _callstack_iter(
        root_callstack, carry, update_indent, callstack_info
    ):
        for line, is_interactive in callstack_info_iterable:
            if first_line is None:
                first_line = line
            if its_the_final_countdown is not None:
                its_the_final_countdown -= 1
                if its_the_final_countdown < 0:
                    break
            outs.append(("[ZeroWidthEscape]", line))
            if is_interactive:
                assert its_the_final_countdown is None
                its_the_final_countdown = max(
                    terminal_height - len(outs), terminal_height // 2
                )

    if outs[0][1] is not first_line:
        outs[0] = ("[ZeroWidthEscape]", "  │ ...")
    assert its_the_final_countdown is not None
    if its_the_final_countdown < 0:
        outs[-1] = ("[ZeroWidthEscape]", "  │ ...")

    new_outs: list[tuple[str, str]] = []
    for line in outs:
        new_outs.append(("[ZeroWidthEscape]", "\n\x1b[2K"))
        new_outs.append(line)
    new_outs[0] = ("[ZeroWidthEscape]", "\r\x1b[2K")
    return list(new_outs)


def _format_source(source: str, first_line_num: int, highlight_line_num: int) -> str:
    syntax_split = _syntax_highlight(source.replace("\t", "    ")).split("\n")

    max_line_num = first_line_num + len(syntax_split) - 1
    len_num = len(str(max_line_num))

    outs = []
    _colour_lookup = ft.cache(_hex_to_rgb)
    for i, syntax_i in enumerate(syntax_split):
        num = i + first_line_num
        if num == highlight_line_num:
            fg_ln = _colour_lookup(_PygmentsStyle.line_number_special_color)
            bg_ln = _colour_lookup(_PygmentsStyle.line_number_special_background_color)
            bg_line = _colour_lookup(_PygmentsStyle.highlight_color)
            arrow = click.style("-> ", bg=bg_line, reset=False)
        else:
            fg_ln = _colour_lookup(_PygmentsStyle.line_number_color)
            bg_ln = _colour_lookup(_PygmentsStyle.line_number_background_color)
            bg_line = _colour_lookup(_PygmentsStyle.background_color)
            arrow = click.style("   ", bg=bg_line, reset=False)
        ln = click.style(f"{{:{len_num}}}".format(num), fg=fg_ln, bg=bg_ln, reset=False)
        line = click.style(syntax_i, bg=bg_line, reset=False)
        outs.append(arrow)
        outs.append(ln)
        outs.append(line)
        # The \x1b[K clear-to-end-of-line code is needed to fill in the background
        # correctly, at least for me. (macOS + iTerm2 + tmux)
        outs.append(" \x1b[K")
        # Must be a separate `.append` to the above, as below we overwrite this entry on
        # the final line.
        outs.append("\n")
    if len(outs) != 0:
        outs[-1] = click.style("", reset=True)  # Remove final newline
    return "".join(outs)


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
        try:
            source_lines, _ = frame.getsourcelines()
            index = frame.line - frame.f_code.co_firstlineno
            if index < 0:
                raise IndexError
            source_line = source_lines[index]
        except (OSError, IndexError):
            # I don't know if the IndexError is ever possible, but just in case.
            source_line = "<no source found>"
        else:
            source_line = _format_source(source_line.rstrip(), frame.line, frame.line)
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


def _make_help(fn_keys):
    key_len = 0
    name_len = 0
    for fn, keys in fn_keys.items():
        key_len = max(key_len, sum(map(len, keys)) + len(keys) - 1)
        name_len = max(name_len, len(_fn_to_name(fn)))
    template = f"{{:{key_len}}}: {{:{name_len}}} - {{}}"
    helpmsg = []
    for fn, keys in fn_keys.items():
        name = _fn_to_name(fn)
        doc = fn.__doc__.split("\n")[0]
        helpmsg.append(template.format("/".join(keys), name, doc))
    helpmsg = "\n".join(helpmsg)
    return helpmsg


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
    """Show the current function's source code."""
    frame = _current_frame(state.location)
    if isinstance(frame, str):
        _echo_first_line(frame)
    else:
        try:
            source = frame.getsource()
        except OSError:
            _echo_first_line("<no source found>")
        else:
            outs = _format_source(
                source.rstrip(), frame.f_code.co_firstlineno, frame.line
            )
            _echo_later_lines(outs)
            _echo_later_lines(f"Currently on line {frame.line}.")
    _echo_newline_end_command()
    return state


# Note that this command is deliberately not an interactive one with `s(t)ack`, in
# which we can scroll through the file or jump to where we are in it. For that there is
# `(e)dit`. (Honestly this command isn't super useful, just because `(e)dit` exists.)
def _show_file(state: _State) -> _State:
    """Show the current file's source code."""
    frame = _current_frame(state.location)
    if isinstance(frame, str):
        _echo_first_line(frame)
    else:
        try:
            filepath = frame.getsourcefile()
            if filepath is None:
                raise TypeError
        except TypeError:
            _echo_first_line("<no source found>")
        else:
            _echo_first_line(_bold(filepath))
            source = pathlib.Path(filepath).read_text().rstrip()
            outs = _format_source(source, 1, frame.line)
            _echo_later_lines(outs)
            _echo_later_lines(f"Currently on line {frame.line}.")
    _echo_newline_end_command()
    return state


def _stack(state: _State) -> _State:
    """Scroll through all frames in all callstacks."""

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

    location = state.location
    skip_hidden = state.skip_hidden
    update_location = False
    short_error = False
    is_callstack_collapsed = {
        callstack: callstack.collapse_default
        for callstack in _callstack_iter(
            state.root_callstack,
            None,
            lambda carry, _: carry,
            lambda callstack, _: callstack,
        )
    }

    def _is_collapsed(callstack: _Callstack):
        return is_callstack_collapsed[callstack]

    def _update(move):
        nonlocal location
        location = move.location

    def _display(event):
        text = _format_callstack_windowed(
            state.root_callstack,
            location,
            state.location,
            _is_collapsed,
            skip_hidden,
            short_error,
        )
        event.app.layout.container.content.text = text
        event.app.reset()

    def _down_frame(event):
        if _is_collapsed(location.callstack):
            return
        move = _move_frame(
            location, skip_hidden=skip_hidden, down=True, include_current_location=False
        )
        _update(move)
        _display(event)

    def _up_frame(event):
        if _is_collapsed(location.callstack):
            return
        move = _move_frame(
            location,
            skip_hidden=skip_hidden,
            down=False,
            include_current_location=False,
        )
        _update(move)
        _display(event)

    def _down_callstack(event):
        move = _move_callstack(
            state.root_callstack,
            location,
            skip_hidden,
            down=True,
        )
        _update(move)
        _display(event)

    def _up_callstack(event):
        move = _move_callstack(
            state.root_callstack,
            location,
            skip_hidden,
            down=False,
        )
        _update(move)
        _display(event)

    def _visibility(event):
        nonlocal skip_hidden
        skip_hidden = not skip_hidden
        _display(event)

    def _toggle_error(event):
        nonlocal short_error
        short_error = not short_error
        _display(event)

    def _toggle_collapse_single(event):
        is_callstack_collapsed[location.callstack] = not _is_collapsed(
            location.callstack
        )
        _display(event)

    def _toggle_collapse_all(event):
        if all(is_callstack_collapsed.values()):
            for key in is_callstack_collapsed.keys():
                is_callstack_collapsed[key] = False
        else:
            for key in is_callstack_collapsed.keys():
                is_callstack_collapsed[key] = True
        _display(event)

    def _stack_select(event):
        nonlocal update_location
        update_location = True
        event.app.exit()

    def _stack_leave(event):
        event.app.exit()

    key_mapping = {
        _down_frame: _config.key_down_frame,
        _up_frame: _config.key_up_frame,
        _down_callstack: _config.key_down_callstack,
        _up_callstack: _config.key_up_callstack,
        _visibility: _config.key_visibility,
        _toggle_error: _config.key_toggle_error,
        _toggle_collapse_single: _config.key_toggle_collapse_single,
        _toggle_collapse_all: _config.key_toggle_collapse_all,
        _stack_select: _config.key_stack_select,
        _stack_leave: _config.key_stack_leave,
    }
    key_bindings, fn_keys, errors = _make_key_bindings(key_mapping)
    for error in errors:
        _echo_later_lines(error)
    text = _format_callstack_windowed(
        state.root_callstack,
        location,
        state.location,
        _is_collapsed,
        skip_hidden,
        short_error,
    )

    container = prompt_toolkit.layout.containers.Window(
        content=prompt_toolkit.layout.controls.FormattedTextControl(
            text=text, show_cursor=False
        ),
        wrap_lines=True,
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
    _echo_later_lines(
        _patdb_info(
            f"Press "
            f"{'/'.join(fn_keys[_down_frame])}, "
            f"{'/'.join(fn_keys[_up_frame])}, "
            f"{'/'.join(fn_keys[_down_callstack])}, "
            f"{'/'.join(fn_keys[_up_callstack])} to scroll; "
            f"{'/'.join(fn_keys[_toggle_error])} to show/hide error messages; "
            f"{'/'.join(fn_keys[_visibility])} to show/hide hidden frames; "
            f"{'/'.join(fn_keys[_toggle_collapse_single])} to show/hide a callstack; "
            f"{'/'.join(fn_keys[_toggle_collapse_all])} to show/hide every callstack; "
            f"{'/'.join(fn_keys[_stack_select])} to switch to a frame; "
            f"{'/'.join(fn_keys[_stack_leave])} to leave stack mode without switching."
            "\n"
        )
    )
    t = threading.Thread(target=app.run)
    t.start()
    t.join()
    if update_location:
        state = dataclasses.replace(state, location=location)
    frame = _current_frame(location)
    if isinstance(frame, str):
        msg = frame
    else:
        msg = _format_frame(frame)
    _echo_first_line(msg)  # `app.run()` adds a newline.
    _echo_newline_end_command()
    return state


def _print(state: _State) -> _State:
    """Prints the value of a variable.

    Printing a variable is such a common thing to do that we break our usual "minimal
    interface" rule, and we do offer a special command for this. (As opposed to opening
    an interpreter and printing the value there.)
    """
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
        text = session.prompt()
    except (EOFError, KeyboardInterrupt):
        return state
    text_strip = text.strip()
    if text_strip == "" or text_strip.startswith("#"):
        return state
    try:
        value = eval(text, globals, locals)
    except BaseException as e:
        value = "\n".join(_format_exception(e, short=False))
    else:
        width = shutil.get_terminal_size().columns
        value = pprint.pformat(
            value, width=width, compact=True, sort_dicts=False, underscore_numbers=True
        )
        value = _syntax_highlight(value)
    _echo_first_line(value)  # `prompt` adds a newline.
    _echo_newline_end_command()
    return dataclasses.replace(state, print_history=history)


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
    filename = frame.f_code.co_filename
    linenumber = str(frame.line)
    line_editor = _config.line_editor
    if line_editor is None:
        editor = _config.editor
        if editor is None:
            _echo_later_lines(
                _patdb_info("Neither EDITOR nor PATDB_EDITOR is configured.")
            )
            result = subprocess.CompletedProcess(args="", returncode=0)
        else:
            result = subprocess.run([editor, filename])
    else:
        result = subprocess.run([line_editor, filename, linenumber])
    if result.returncode != 0:
        _echo_later_lines(_patdb_info(f"Error with returncode {result.returncode}"))
    _echo_newline_end_command()
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
    depth = _config.depth
    if depth is None:
        depth_int = 0
    else:
        depth_int = depth
    try:
        _config.depth = depth_int + 1
        _echo_later_lines("")
        ptpython.repl.embed(
            globals,
            locals,
            configure=_ptpython_configure,
            history_filename=str(_patdb_history_file),
        )
    except SystemExit:
        pass
    finally:
        if depth is None:
            del _config.depth
        else:
            _config.depth = depth
    # We already have a spurious newline from the interpreter
    # _echo_newline_end_command()
    return state


def _visibility(state: _State) -> _State:
    """Toggles skipping hidden frames in other commands."""
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
    _echo_first_line("Quitting.")
    _echo_newline_end_command()
    sys.exit()


def _help(state: _State) -> _State:
    """Display a list of all debugger commands."""
    _echo_later_lines(state.helpmsg)
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

    #
    # Step 1: figure out how we're being called, and get the callstacks.
    #

    e: Union[None, BaseException, types.TracebackType]
    if len(args) == 0:
        e = None
    elif len(args) == 1:
        [e] = args
    elif len(args) == 3:
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
            return
        if isinstance(e, bdb.BdbQuit):
            # If someone has mix-and-matched with bdb or pdb then don't raise on those.
            return
        if isinstance(e, SystemExit):
            # We definitely don't to intercept this one!
            return
        root_callstack = _get_callstacks_from_error(
            e,
            up_callstack=None,
            kinds=frozenset([_CallstackKind.toplevel]),
            collapse_default=False,
        )
    else:
        if e is None:
            # Called as an explicit `breakpoint()`.
            frames = tuple(
                _Frame(x.frame, x.frame.f_lineno)
                for x in inspect.stack()[stacklevel:][::-1]
            )
        elif isinstance(e, types.TracebackType):
            # Called as an explicit `patdb.debug(some_traceback)`.
            frames = []
            while e is not None:
                frames.append(_Frame(e.tb_frame, e.tb_lineno))
                e = e.tb_next
            frames = tuple(frames)
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
        _edit: _config.key_edit,
        _interpret: _config.key_interpret,
        _visibility: _config.key_visibility,
        _continue: _config.key_continue,
        _quit: _config.key_quit,
        _help: _config.key_help,
    }
    key_bindings_, fn_keys, errors = _make_key_bindings(key_mapping)
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
    helpmsg = _make_help(fn_keys)

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
    state = _State(
        # Replaceable
        done=False,
        skip_hidden=True,
        location=_Location(root_callstack, frame_idx),
        # Not replaceable
        print_history=prompt_toolkit.history.InMemoryHistory(),
        helpmsg=helpmsg,
        root_callstack=root_callstack,
    )

    #
    # Step 5: print header information
    #
    frame = _current_frame(state.location)
    if isinstance(frame, str):
        frame_info = frame
    else:
        frame_info = _format_frame(frame)
    click.echo(frame_info)
    if e is not None:
        click.echo("\n".join(_format_exception(e, short=False)))
    try:
        helpkeys = fn_keys[_help]
    except KeyError:
        # It could occur that this someone has rebound away the help key, or had a
        # keybinding clash.
        pass
    else:
        helpkeys = "/".join(helpkeys)
        click.echo(_patdb_info(f"Press {helpkeys} for a list of all commands."))
        del helpkeys
    del fn_keys

    #
    # Step 6: run the REPL!
    #
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
    prompt = _patdb_prompt()
    while not state.done:
        click.echo(prompt, nl=False)
        t = threading.Thread(target=app.run)
        t.start()
        t.join()
        assert detected_fn is not None
        assert detected_keys is not None
        # Convention on \n:
        #
        # We split up the response of each command into the "first line" (appears on
        # the same line as the prompt and the detected keys) and the "later lines"
        # (appears on subsequent lines).
        # Every command should call the `_echo_first_line` or `_echo_later_lines`
        # functions to do the right thing.
        # Every command should end with a call to `_echo_newline_end_command` to insert
        # the newline for the next prompt.
        #
        # We let each command handle doing this, as someone of them call out to other
        # processes, which don't always do consistent things. This offers some wiggle
        # room as an escape hatch. (E.g. `interact` leaves off
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
