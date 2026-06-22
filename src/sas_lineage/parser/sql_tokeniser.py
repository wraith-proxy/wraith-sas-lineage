"""
Stdlib PROC SQL tokeniser.

A flat regex cannot see paren depth, string literals, or comma-joins, so the
FROM/JOIN table list, subquery boundaries and select-list commas were all
mis-split (F2/F3/F5). This does a single left-to-right scan that skips string
literals and tracks paren depth, then walks the tokens with a depth-keyed
context stack to harvest table references. Comma-joins and tables nested
inside subqueries are included (each FROM at any depth opens its own context,
so nested FROMs are harvested without explicit recursion).

Ported idiomatically from DATALineage/R/proc_sql.R.
"""

from __future__ import annotations

import re
from typing import NamedTuple

# Dotted so a qualified ref (LIB.TBL, a.col) is one token, not three.
_IDENT = re.compile(r"[A-Za-z_][\w.]*")
_MACRO = re.compile(r"&\w+")

# Keywords that end a FROM table list.
# Clause-starters (where/group/order/…) terminate the whole list; JOIN
# modifiers (inner/left/right/full/outer/natural/cross) and the bare `join`
# keyword close the preceding context so each join gets its own slice; `on`
# closes the join's own slice before the ON condition.
_TABLE_LIST_END = frozenset(
    {
        "where",
        "group",
        "order",
        "having",
        "union",
        "except",
        "intersect",
        "qualify",
        "window",
        "select",
        "inner",
        "left",
        "right",
        "full",
        "outer",
        "natural",
        "cross",
        "join",
        "on",
    }
)

# (libref|None, table, alias|None). table keeps a leading & for macro refs.
TableRef = tuple[str | None, str, str | None]


class Token(NamedTuple):
    kind: str  # ident | open | close | comma | semi
    value: str  # lowercased for idents/macros; literal for punctuation
    start: int
    end: int
    depth: int


def _skip_string(buf: str, i: int, quote: str) -> int:
    """Return the index just past the closing quote, treating doubled
    quotes ('' / "") as an escaped quote, not a terminator."""
    i += 1  # skip opening quote
    n = len(buf)
    while i < n:
        if buf[i] == quote:
            # doubled quote = escape; single quote = end
            if i + 1 < n and buf[i + 1] == quote:
                i += 2
            else:
                i += 1
                break
        else:
            i += 1
    return i


def scan_tokens(buffer: str) -> list[Token]:
    """Single L→R scan: skip strings, track paren depth, emit tokens."""
    tokens: list[Token] = []
    i, n, depth = 0, len(buffer), 0
    while i < n:
        c = buffer[i]
        if c in "'\"":
            i = _skip_string(buffer, i, c)
            continue
        if c == "(":
            depth += 1
            tokens.append(Token("open", "(", i, i + 1, depth))
            i += 1
            continue
        if c == ")":
            depth -= 1
            tokens.append(Token("close", ")", i, i + 1, depth))
            i += 1
            continue
        if c == ",":
            tokens.append(Token("comma", ",", i, i + 1, depth))
            i += 1
            continue
        if c == ";":
            tokens.append(Token("semi", ";", i, i + 1, depth))
            i += 1
            continue
        if c == "&":
            m = _MACRO.match(buffer, i)
            if m:
                tokens.append(
                    Token("ident", m.group(0).lower(), i, m.end(), depth)
                )
                i = m.end()
                continue
            i += 1
            continue
        m = _IDENT.match(buffer, i)
        if m:
            tokens.append(
                Token("ident", m.group(0).lower(), i, m.end(), depth)
            )
            i = m.end()
            continue
        i += 1
    return tokens


def _parse_slice(chunk: str) -> TableRef | None:
    """Parse a harvested ``[libref.]table [as alias]`` slice into a TableRef.

    A slice that starts with ``(`` is a derived table. Skip it; its inner
    tables were already harvested by their own FROM context (F2).
    """
    chunk = chunk.strip()
    if not chunk or chunk.startswith("("):
        return None
    parts = chunk.split()
    ref = parts[0]
    alias = None
    if len(parts) >= 3 and parts[1].lower() == "as":
        alias = parts[2]
    elif len(parts) >= 2 and parts[1].lower() != "as":
        alias = parts[1]
    if ref.startswith("&"):
        return (None, ref, alias)
    libref, _, table = ref.partition(".")
    if table:
        # A.B.C → table still contains a dot; three-part ref is unparseable.
        # Use sentinel so _build_sources can emit a Flag (flag-never-drop).
        if "." in table:
            return ("__UNPARSEABLE__", ref, alias)
        return (libref, table, alias)
    return (None, ref, alias)


def extract_sql_tables(buffer: str) -> list[TableRef]:
    """Harvest every FROM/JOIN table ref: comma-joins and nested included."""
    refs: list[TableRef] = []
    stack: list[dict] = []  # each: {kind, depth, list_start, commas}

    def close_top(end_idx: int) -> None:
        ctx = stack.pop()
        if ctx["list_start"] is None:
            return
        bounds = [ctx["list_start"], *ctx["commas"], end_idx]
        for idx in range(len(bounds) - 1):
            lo = bounds[idx] + (1 if idx > 0 else 0)
            ref = _parse_slice(buffer[lo : bounds[idx + 1]])
            if ref is not None:
                refs.append(ref)

    for kind, value, start, end, depth in scan_tokens(buffer):
        if kind == "ident":
            if value in ("from", "join"):
                # A JOIN ends the preceding table list before starting its own;
                # its own table+alias are harvested when its terminator (on /
                # where / next join / ;) closes it, so the alias is kept.
                if value == "join" and stack and stack[-1]["depth"] == depth:
                    close_top(start)
                stack.append(
                    {
                        "kind": value,
                        "depth": depth,
                        "list_start": None,
                        "commas": [],
                    }
                )
            elif value in _TABLE_LIST_END and stack:
                if stack[-1]["depth"] == depth:
                    close_top(start)
            elif stack:
                top = stack[-1]
                if top["depth"] == depth and top["list_start"] is None:
                    top["list_start"] = start
        elif kind == "open":
            if stack:
                top = stack[-1]
                if top["depth"] == depth - 1 and top["list_start"] is None:
                    top["list_start"] = start
        elif kind == "close":
            while stack and stack[-1]["depth"] > depth:
                close_top(start)
        elif kind == "comma":
            if stack:
                top = stack[-1]
                if top["kind"] == "from" and top["depth"] == depth:
                    top["commas"].append(start)
        elif kind == "semi":
            while stack:
                close_top(start)

    while stack:
        close_top(len(buffer))
    return refs
