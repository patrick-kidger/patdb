import dataclasses
import difflib
import functools as ft
import sys
import types
from collections.abc import Callable, Iterable, Sequence
from typing import Any, cast, NamedTuple

from ._wadler_lindig import (
    AbstractDoc,
    BreakDoc,
    ConcatDoc,
    GroupDoc,
    NestDoc,
    pretty_format,
    TextDoc,
)


class _WithRepr:
    def __init__(self, string: str):
        self.string = string

    def __repr__(self) -> str:
        return self.string


comma = ConcatDoc((TextDoc(","), BreakDoc(" ")))


def join(sep: AbstractDoc, objs: Sequence[AbstractDoc]) -> AbstractDoc:
    if len(objs) == 0:
        return ConcatDoc(())
    pieces = [objs[0]]
    for obj in objs[1:]:
        pieces.append(sep)
        pieces.append(obj)
    return ConcatDoc(tuple(pieces))


def bracketed(
    name: None | AbstractDoc,
    indent: int,
    objs: Sequence[AbstractDoc],
    lbracket: str,
    rbracket: str,
    sep: AbstractDoc = comma,
) -> AbstractDoc:
    objs = [GroupDoc(x) for x in objs]
    if len(objs) == 0:
        nested = ConcatDoc(())  # In particular no BreakDocs.
    else:
        nested = ConcatDoc(
            (NestDoc(ConcatDoc((BreakDoc(""), join(sep, objs))), indent), BreakDoc(""))
        )
    pieces = []
    if name is not None:
        pieces.append(name)
    pieces.extend([TextDoc(lbracket), nested, TextDoc(rbracket)])
    return GroupDoc(ConcatDoc(tuple(pieces)))


def named_objs(pairs: Iterable[tuple[Any, Any]], **kwargs):
    return [
        ConcatDoc((TextDoc(key), TextDoc("="), pdoc(value, **kwargs)))
        for key, value in pairs
    ]


def array_summary(shape: tuple[int, ...], dtype: str, kind: None | str) -> AbstractDoc:
    short_dtype = (
        dtype.replace("float", "f")
        .replace("uint", "u")
        .replace("int", "i")
        .replace("complex", "c")
    )
    short_shape = ",".join(map(str, shape))
    out = f"{short_dtype}[{short_shape}]"
    if kind is not None:
        out = out + f"({kind})"
    return TextDoc(out)


def _pformat_list(obj: list, **kwargs) -> AbstractDoc:
    return bracketed(
        name=None,
        indent=kwargs["indent"],
        objs=[pdoc(x, **kwargs) for x in obj],
        lbracket="[",
        rbracket="]",
    )


def _pformat_set(obj: set, **kwargs) -> AbstractDoc:
    return bracketed(
        name=None,
        indent=kwargs["indent"],
        objs=[pdoc(x, **kwargs) for x in obj],
        lbracket="{",
        rbracket="}",
    )


def _pformat_frozenset(obj: frozenset, **kwargs) -> AbstractDoc:
    return bracketed(
        name=TextDoc("frozenset"),
        indent=kwargs["indent"],
        objs=[pdoc(x, **kwargs) for x in obj],
        lbracket="({",
        rbracket="})",
    )


def _pformat_tuple(obj: tuple, **kwargs) -> AbstractDoc:
    if len(obj) == 1:
        objs = [ConcatDoc((pdoc(obj[0], **kwargs), TextDoc(",")))]
    else:
        objs = [pdoc(x, **kwargs) for x in obj]
    return bracketed(
        name=None, indent=kwargs["indent"], objs=objs, lbracket="(", rbracket=")"
    )


def _pformat_namedtuple(obj: NamedTuple, **kwargs) -> AbstractDoc:
    objs = named_objs([(name, getattr(obj, name)) for name in obj._fields], **kwargs)
    return bracketed(
        name=TextDoc(obj.__class__.__name__),
        indent=kwargs["indent"],
        objs=objs,
        lbracket="(",
        rbracket=")",
    )


def _dict_entry(key: Any, value: Any, **kwargs) -> AbstractDoc:
    return ConcatDoc(
        (pdoc(key, **kwargs), TextDoc(":"), BreakDoc(" "), pdoc(value, **kwargs))
    )


def _pformat_dict(obj: dict, **kwargs) -> AbstractDoc:
    objs = [_dict_entry(key, value, **kwargs) for key, value in obj.items()]
    return bracketed(
        name=None,
        indent=kwargs["indent"],
        objs=objs,
        lbracket="{",
        rbracket="}",
    )


def _array_kind(x) -> None | str:
    # For pragmatic reasons we ship with support for NumPy + PyTorch + JAX out of the
    # box.
    for module, array in [("numpy", "ndarray"), ("torch", "Tensor"), ("jax", "Array")]:
        if module in sys.modules and isinstance(x, getattr(sys.modules[module], array)):
            return module
    return None


def _pformat_ndarray(obj, **kwargs) -> AbstractDoc:
    short_arrays = kwargs["short_arrays"]
    if short_arrays:
        kind = _array_kind(obj)
        assert kind is not None
        *_, dtype = str(obj.dtype).rsplit(".")
        return array_summary(obj.shape, dtype, kind)
    return TextDoc(repr(obj))


def _pformat_partial(obj: ft.partial, **kwargs) -> AbstractDoc:
    objs = (
        [pdoc(obj.func, **kwargs)]
        + [pdoc(x, **kwargs) for x in obj.args]
        + named_objs(obj.keywords.items(), **kwargs)
    )
    return bracketed(
        name=TextDoc("partial"),
        indent=kwargs["indent"],
        objs=objs,
        lbracket="(",
        rbracket=")",
    )


def _pformat_function(obj: types.FunctionType, **kwargs) -> AbstractDoc:
    del kwargs
    if hasattr(obj, "__wrapped__"):
        fn = "wrapped function"
    else:
        fn = "function"
    return TextDoc(f"<{fn} {obj.__name__}>")


def _pformat_dataclass(obj, **kwargs) -> AbstractDoc:
    objs = named_objs(
        [
            (field.name, getattr(obj, field.name, _WithRepr("<uninitialised>")))
            for field in dataclasses.fields(obj)
            if field.repr
        ],
        **kwargs,
    )
    return bracketed(
        name=TextDoc(obj.__class__.__name__),
        indent=kwargs["indent"],
        objs=objs,
        lbracket="(",
        rbracket=")",
    )


def pdoc(
    obj: Any,
    indent: int = 2,
    short_arrays: bool = True,
    custom: Callable[[Any], None | AbstractDoc] = lambda _: None,
    **kwargs,
) -> AbstractDoc:
    """Formats an object into a Wadler--Lindig pretty doc. Such documents are
    essentially strings that haven't yet been pretty-formatted to a particular width.

    **Arguments:**

    - `obj`: the object to pretty-doc.
    - `indent`: when the contents of a structured type are too large to fit on one line,
        they will be indented by this amount and placed on separate lines.
    - `short_arrays`: whether to print a NumPy array / PyTorch tensor / JAX array as a
        short summary of the form `f32[3,4]` (here indicating a `float32` matrix of
        shape `(3, 4)`)
    - `custom`: a way to pretty-doc custom types. This will be called on every object it
        encounters. If its return is `None` then the usual behaviour will be performed.
        If its return is an `AbstractDoc` then that will be used instead.
    - `**kwargs`: all kwargs are forwarded on to all `__pp__` calls, as an
        escape hatch for custom behaviour.

    **Returns:**

    A pretty-doc representing `obj`.

    !!! info

        The behaviour of this function can be customised in two ways.

        First, any object which implements a
        `__pp__(self) -> None | AbstractDoc` method will have that method
        called to determine its pretty-doc.

        Second, the `custom` argument to this function can be used. This is particularly
        useful to provide custom pretty-docs for objects provided by third-party
        libraries. (For which you cannot add a `__pp__` method.)
    """

    kwargs["indent"] = indent
    kwargs["short_arrays"] = short_arrays
    kwargs["custom"] = custom

    if isinstance(obj, AbstractDoc):
        return obj

    maybe_custom = custom(obj)
    if maybe_custom is not None:
        return maybe_custom

    if hasattr(type(obj), "__pp__"):
        custom_pp = obj.__pp__(**kwargs)
        if isinstance(custom_pp, AbstractDoc):
            return GroupDoc(custom_pp)
        # else it's some non-pretty-print `__pp__` method; ignore.

    if isinstance(obj, tuple):
        if hasattr(obj, "_fields"):
            return _pformat_namedtuple(cast(NamedTuple, obj), **kwargs)
        return _pformat_tuple(obj, **kwargs)
    if isinstance(obj, list):
        return _pformat_list(obj, **kwargs)
    if isinstance(obj, dict):
        return _pformat_dict(obj, **kwargs)
    if isinstance(obj, set):
        return _pformat_set(obj, **kwargs)
    if isinstance(obj, frozenset):
        return _pformat_frozenset(obj, **kwargs)
    if _array_kind(obj) is not None:
        return _pformat_ndarray(obj, **kwargs)
    if isinstance(obj, ft.partial):
        return _pformat_partial(obj, **kwargs)
    if isinstance(obj, types.FunctionType):
        return _pformat_function(obj, **kwargs)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return _pformat_dataclass(obj, **kwargs)
    # str, bool, int, float, complex etc.
    return TextDoc(repr(obj))


def pformat(
    obj: Any,
    *,
    width: int = 88,
    indent: int = 2,
    follow_wrapped: bool = True,
    short_arrays: bool = True,
    custom: Callable[[Any], None | AbstractDoc] = lambda _: None,
    **kwargs,
) -> str:
    """Pretty-formats an object as a string.

    **Arguments:**

    - `obj`: the object to pretty-doc.
    - `width`: a best-effort maximum width to allow. May be exceeded if there are
        unbroken pieces of text which are wider than this.
    - `indent`: when the contents of a structured type are too large to fit on one line,
        they will be indented by this amount and placed on separate lines.
    - `follow_wrapped`: whether to unwrap `__wrapped__` and `functools.partial` objects.
    - `short_arrays`: whether to print a NumPy array / PyTorch tensor / JAX array as a
        short summary of the form `f32[3,4]` (here indicating a `float32` matrix of
        shape `(3, 4)`)
    - `custom`: a way to pretty-doc custom types. This will be called on every object it
        encounters. If its return is `None` then the usual behaviour will be performed.
        If its return is an `AbstractDoc` then that will be used instead.
    - `**kwargs`: all kwargs are forwarded on to all `__pp__` calls, as an
        escape hatch for custom behaviour.

    **Returns:**

    A string representing `obj`.

    !!! info

        The behaviour of this function can be customised in two ways.

        First, any object which implements a
        `__pp__(self) -> None | AbstractDoc` method will have that method
        called to determine its pretty-doc.

        Second, the `custom` argument to this function can be used. This is particularly
        useful to provide custom pretty-docs for objects provided by third-party
        libraries. (For which you cannot add a `__pp__` method.)
    """

    doc = pdoc(
        obj,
        indent=indent,
        follow_wrapped=follow_wrapped,
        short_arrays=short_arrays,
        custom=custom,
        **kwargs,
    )
    return pretty_format(doc, width)


def pprint(obj: Any, **kwargs) -> None:
    """As `pformat`, but prints its result to stdout."""

    print(pformat(obj, **kwargs))


def pdiff(p_minus: str, p_plus: str) -> str:
    """Returns a pretty-diff between two strings.

    You may want to use `pformat` to produce those strings.
    """
    diff = difflib.ndiff(p_minus.splitlines(), p_plus.splitlines())
    diff = "\n".join(line for line in diff if not line.startswith("?"))
    return diff


def ansi_format(text: str, color: str, bold: bool) -> str:
    """Formats `text` with a foreground color `color`, and optionally mark it `bold`,
    using ANSI color codes.
    """
    color_code = {
        "black": "\x1b[30m",
        "red": "\x1b[31m",
        "green": "\x1b[32m",
        "yellow": "\x1b[33m",
        "blue": "\x1b[34m",
        "magenta": "\x1b[35m",
        "cyan": "\x1b[36m",
        "white": "\x1b[37m",
    }[color]
    out = color_code + text + "\x1b[0m"
    if bold:
        out = "\x1b[1m" + out
    return out
