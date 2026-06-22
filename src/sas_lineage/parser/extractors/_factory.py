"""
Shared Table/Column factories for extractors.

Emitted tables/columns are placeholders: engine/path/layer carry defaults
that the builder fills in from the owning LIBNAME (see
`ProvenanceBuilder._resolve_librefs`). Centralised so every extractor agrees
on those defaults rather than copying the same literals.
"""

from __future__ import annotations

from sas_lineage.ids import column_id as make_col_id
from sas_lineage.ids import table_id as make_table_id
from sas_lineage.models import Column, Flag, Layer, Table, UnmappableReason
from sas_lineage.parser import patterns
from sas_lineage.parser.log_resolver import LogResolver


def flag_macro(
    text: str,
    resolver: LogResolver,
    ref_id: str,
    flags: list[Flag],
) -> None:
    """Flag an unresolved macro, distinguishing DI autogen column names.

    Resolves first (log, then code %LET fallback); a name resolved there
    raises no flag. DI autogen column macros (&input_N_col_name) get the
    DYNAMIC_COLUMN_NAME reason; anything else MACRO_UNRESOLVED.
    """
    _, ok = resolver.resolve(text)
    if ok:
        return
    if patterns.DI_AUTOGEN_COL.search(text):
        reason = UnmappableReason.DYNAMIC_COLUMN_NAME
        context = "DI autogen column macro unresolved"
    else:
        reason = UnmappableReason.MACRO_UNRESOLVED
        context = "unresolved macro in expression"
    flags.append(
        Flag(
            ref_id=ref_id,
            reason=reason,
            context=context,
            snippet=text[:200],
        )
    )


def new_table(libref: str, name: str) -> Table:
    return Table(
        id=make_table_id(libref, name),
        name=name,
        libref=libref,
        engine="BASE",
        path="",
        layer=Layer.RAW,
        is_remote=False,
    )


def new_column(table_id: str, name: str) -> Column:
    return Column(
        id=make_col_id(table_id, name),
        table_id=table_id,
        name=name,
        layer=Layer.RAW,
        data_type="UNKNOWN",
        nullable=True,
    )
