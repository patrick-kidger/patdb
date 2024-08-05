import dataclasses
import functools as ft
import sys
import types
from collections.abc import Callable, Sequence
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


def join(sep: AbstractDoc, objs: Sequence[AbstractDoc]):
    if len(objs) == 0:
        return ConcatDoc()
    else:
        pieces = [objs[0]]
        for obj in objs[1:]:
            pieces.append(sep)
            pieces.append(obj)
        return ConcatDoc(*pieces)


def bracketed(
    name: None | AbstractDoc,
    indent: int,
    objs: Sequence[AbstractDoc],
    lbracket: str,
    rbracket: str,
) -> AbstractDoc:
    comma = ConcatDoc(TextDoc(","), BreakDoc(" "))
    objs = [GroupDoc(x) for x in objs]
    nested = ConcatDoc(
        NestDoc(ConcatDoc(BreakDoc(""), join(comma, objs)), indent), BreakDoc("")
    )
    pieces = []
    if name is not None:
        pieces.append(name)
    pieces.extend([TextDoc(lbracket), nested, TextDoc(rbracket)])
    return GroupDoc(ConcatDoc(*pieces))


def named_objs(pairs, **kwargs):
    return [
        ConcatDoc(TextDoc(key), TextDoc("="), pdoc(value, **kwargs))
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


def _pformat_tuple(obj: tuple, **kwargs) -> AbstractDoc:
    if len(obj) == 1:
        objs = [ConcatDoc(pdoc(obj[0], **kwargs), TextDoc(","))]
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
        pdoc(key, **kwargs), TextDoc(":"), BreakDoc(" "), pdoc(value, **kwargs)
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
    else:
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
    if kwargs.get("wrapped", False):
        fn = "wrapped function"
    else:
        fn = "function"
    return TextDoc(f"<{fn} {obj.__name__}>")


def _pformat_dataclass(obj, **kwargs) -> AbstractDoc:
    objs = named_objs(
        [
            (field.name, getattr(obj, field.name))
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
    follow_wrapped: bool = True,
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
    - `follow_wrapped`: whether to unwrap `__wrapped__` and `functools.partial` objects.
    - `short_arrays`: whether to print a NumPy array / PyTorch tensor / JAX array as a
        short summary of the form `f32[3,4]` (here indicating a `float32` matrix of
        shape `(3, 4)`)
    - `custom`: a way to pretty-doc custom types. This will be called on every object it
        encounters. If its return is `None` then the usual behaviour will be performed.
        If its return is an `AbstractDoc` then that will be used instead.
    - `**kwargs`: all kwargs are forwarded on to all `__kidgerbase_pdoc__` calls, as an
        escape hatch for custom behaviour.

    **Returns:**

    A pretty-doc representing `obj`.

    !!! info

        The behaviour of this function can be customised in two ways.

        First, any object which implements a
        `__kidgerbase_pdoc__(self) -> None | AbstractDoc` method will have that method
        called to determine its pretty-doc.

        Second, the `custom` argument to this function can be used. This is particularly
        useful to provide custom pretty-docs for objects provided by third-party
        libraries. (For which you cannot add a `__kidgerbase_pdoc__` method.)
    """

    kwargs["indent"] = indent
    kwargs["follow_wrapped"] = follow_wrapped
    kwargs["short_arrays"] = short_arrays

    if isinstance(obj, AbstractDoc):
        return obj

    maybe_custom = custom(obj)
    if maybe_custom is not None:
        return maybe_custom

    if hasattr(obj, "__kidgerbase_pdoc__"):
        custom_pp = obj.__kidgerbase_pdoc__(**kwargs)
        if custom_pp is not None:
            return GroupDoc(custom_pp)

    if isinstance(obj, tuple):
        if hasattr(obj, "_fields"):
            return _pformat_namedtuple(cast(NamedTuple, obj), **kwargs)
        else:
            return _pformat_tuple(obj, **kwargs)
    elif isinstance(obj, list):
        return _pformat_list(obj, **kwargs)
    elif isinstance(obj, dict):
        return _pformat_dict(obj, **kwargs)
    elif _array_kind(obj) is not None:
        return _pformat_ndarray(obj, **kwargs)
    elif follow_wrapped and hasattr(obj, "__wrapped__"):
        return pdoc(obj.__wrapped__, wrapped=True, **kwargs)
    elif isinstance(obj, ft.partial):
        return _pformat_partial(obj, **kwargs)
    elif isinstance(obj, types.FunctionType):
        return _pformat_function(obj, **kwargs)
    elif dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return _pformat_dataclass(obj, **kwargs)
    else:  # str, bool, int, float, complex etc.
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
    """Pretty-formats an object into a string.

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
    - `**kwargs`: all kwargs are forwarded on to all `__kidgerbase_pdoc__` calls, as an
        escape hatch for custom behaviour.

    **Returns:**

    A string representing `obj`.

    !!! info

        The behaviour of this function can be customised in two ways.

        First, any object which implements a
        `__kidgerbase_pdoc__(self) -> None | AbstractDoc` method will have that method
        called to determine its pretty-doc.

        Second, the `custom` argument to this function can be used. This is particularly
        useful to provide custom pretty-docs for objects provided by third-party
        libraries. (For which you cannot add a `__kidgerbase_pdoc__` method.)
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


def pprint(
    obj: Any,
    *,
    width: int = 88,
    indent: int = 2,
    follow_wrapped: bool = True,
    short_arrays: bool = True,
    custom: Callable[[Any], None | AbstractDoc] = lambda _: None,
    **kwargs,
) -> None:
    """As `pformat`, but prints its result to stdout."""

    print(
        pformat(
            obj,
            width=width,
            indent=indent,
            follow_wrapped=follow_wrapped,
            short_arrays=short_arrays,
            custom=custom,
            *kwargs,
        )
    )
