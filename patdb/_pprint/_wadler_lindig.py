"""An improved Wadler--Lindig pretty printer.

This implementation additionally:

- handles new lines in the text to format.
- removes some dead code from the canonical implementation.

References:

(1) Wadler, P., 1998. A prettier printer.
    Journal of Functional Programming, pp.223-244.
(2) Lindig, C. 2000. Strictly Pretty.
    https://lindig.github.io/papers/strictly-pretty-2000.pdf

Inspired by JAX's use of the same references above, but re-implemented from scratch.
"""

import re
from dataclasses import dataclass


class AbstractDoc:
    pass


@dataclass(frozen=True)
class TextDoc(AbstractDoc):
    text: str


@dataclass(frozen=True)
class ConcatDoc(AbstractDoc):
    children: tuple[AbstractDoc, ...]


@dataclass(frozen=True)
class NestDoc(AbstractDoc):
    child: AbstractDoc
    indent: int


@dataclass(frozen=True)
class BreakDoc(AbstractDoc):
    text: str

    def __post_init__(self):
        if "\n" in self.text:
            raise ValueError("Cannot have newlines in BreakDocs.")


@dataclass(frozen=True)
class GroupDoc(AbstractDoc):
    child: AbstractDoc


def _remove_ansi(x: str) -> str:
    return re.sub(r"\033\[[;?0-9]*[a-zA-Z]", "", x)


# The implementation in both Lindig and JAX additionally tracks an indent and a mode...
# which both seem to just go entirely unused? We don't include them here.
def _fits(doc: AbstractDoc, width: int) -> bool:
    todo: list[AbstractDoc] = [doc]
    while len(todo) > 0 and width >= 0:
        match todo.pop():
            case TextDoc(text):
                width -= max(
                    (len(line) for line in _remove_ansi(text).splitlines()), default=0
                )
            case ConcatDoc(children):
                todo.extend(reversed(children))
            case NestDoc(child, _):
                todo.append(child)
            case BreakDoc(text):
                width -= len(_remove_ansi(text))
            case GroupDoc(child):
                todo.append(child)
            case _:
                assert False
    return width >= 0


def pretty_format(doc: AbstractDoc, width: int) -> str:
    """Pretty-formats a document using a Wadler--Lindig pretty-printer.

    **Arguments:**

    - `doc`: a document to pretty-format as a string.
    - `width`: a best-effort maximum width to allow. May be exceeded if there are
        unbroken pieces of text which are wider than this.

    **Returns:**

    A string, corresponding to the pretty-printed document.

    !!! info

        We extend the canonical Wadler--Lindig implementation with the ability to handle
        multiline text. We also remove what seems to be some dead code from their
        implementation.
    """
    outs: list[str] = []
    width_so_far = 0
    # JAX starts in break-mode whilst Lindig defaults to flat-mode. The latter makes
    # more sense, I think.
    todo: list[tuple[int, bool, AbstractDoc]] = [(0, False, GroupDoc(doc))]
    while len(todo) > 0:
        match todo.pop():
            case indent, _, TextDoc(text):
                outs.append(text.replace("\n", "\n" + " " * width_so_far))
                width_so_far += len(_remove_ansi(text.rsplit("\n", 1)[-1]))
            case indent, flat, ConcatDoc(children):
                todo.extend((indent, flat, child) for child in reversed(children))
            case indent, flat, NestDoc(child, new_indent):
                todo.append((indent + new_indent, flat, child))
            case indent, flat, BreakDoc(text):
                if flat:
                    outs.append(text)
                    width_so_far += len(_remove_ansi(text))
                else:
                    outs.append("\n" + " " * indent)
                    width_so_far = indent
            case indent, _, GroupDoc(child):
                todo.append((indent, _fits(child, width - width_so_far), child))
            case _:
                assert False
    return "".join(outs)
