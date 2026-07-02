"""
LIBNAME extractor: discovers library references and infers layer/path.
"""

from __future__ import annotations

import re

from sas_lineage.ids import table_id as make_table_id
from sas_lineage.models import Column, Flag, Layer, LineageChain, Table
from sas_lineage.parser import patterns
from sas_lineage.parser.log_resolver import LogResolver

_LAYER_HINTS: dict[str, Layer] = {
    "raw": Layer.RAW,
    "ods": Layer.ODS,
    "ods": Layer.ODS,
    "stg": Layer.STG,
    "stg": Layer.STG,
    "mart": Layer.MART,
    "mart": Layer.MART,
}


class LibnameExtractor:
    """Extracts LIBNAME statements from a code block."""

    def can_extract(self, code_block: str) -> bool:
        return bool(patterns.LIBNAME_STMT.search(code_block))

    def extract(
        self,
        code_block: str,
        resolver: LogResolver,
        job_id: str,
        step_name: str,
    ) -> tuple[list[Table], list[Column], list[LineageChain], list[Flag]]:
        tables: list[Table] = []

        for line in code_block.splitlines():
            line_clean = patterns.C_COMMENT_FULL.sub("", line).strip()
            if not line_clean:
                continue

            m_lib = patterns.LIBNAME_STMT.search(line_clean)
            if not m_lib:
                continue

            libref = m_lib.group(1).upper()

            path, path_resolved = "", True
            m_path = patterns.LIBNAME_PATH.search(line_clean)
            if m_path:
                raw_path = m_path.group(1)
                path, path_resolved = resolver.resolve(raw_path)

            engine = "BASE"
            if re.search(r"\bdb2\b", line_clean, re.IGNORECASE):
                engine = "DB2"
            elif re.search(r"\bodbc\b", line_clean, re.IGNORECASE):
                engine = "ODBC"

            m_slibref = patterns.LIBNAME_SLIBREF.search(line_clean)
            if m_slibref or re.search(
                r"\bslibref\b", line_clean, re.IGNORECASE
            ):
                engine = "REMOTE"

            # Remote/DB librefs have no filesystem path; capture the logical
            # locator (server alias or database name) as the path instead.
            if not path:
                if engine == "REMOTE" and m_slibref:
                    server, _ = resolver.resolve(m_slibref.group(3))
                    path = server.upper()
                elif engine in {"DB2", "ODBC"}:
                    m_db2 = patterns.LIBNAME_DB2.search(line_clean)
                    if m_db2:
                        path = m_db2.group(1).upper()

            is_remote = engine == "REMOTE"
            layer = _infer_layer(libref, path)

            tid = make_table_id(libref, libref)
            tables.append(
                Table(
                    id=tid,
                    name=libref,
                    libref=libref,
                    engine=engine,
                    path=path,
                    layer=layer,
                    is_remote=is_remote,
                )
            )

        return tables, [], [], []


def _infer_layer(libref: str, path: str) -> Layer:
    combined = (libref + " " + path).lower()
    for hint, layer in _LAYER_HINTS.items():
        if hint in combined:
            return layer
    return Layer.RAW
