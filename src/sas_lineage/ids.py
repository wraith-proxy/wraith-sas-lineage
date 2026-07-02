"""Content-hashed stable IDs: re-runs produce diffable output."""

import hashlib


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:12]


def table_id(libref: str, name: str) -> str:
    return f"tbl_{_hash(f'{libref.upper()}.{name.upper()}')}"


def column_id(table_id: str, name: str) -> str:
    return f"col_{_hash(f'{table_id}.{name.upper()}')}"


def job_id(name: str) -> str:
    return f"job_{_hash(name.upper())}"


def lineage_chain_id(
    mart_col_id: str, source_col_id: str, chain_order: int
) -> str:
    return f"lc_{_hash(f'{mart_col_id}.{source_col_id}.{chain_order}')}"


def table_lineage_id(
    source_table_id: str, target_table_id: str, step_name: str
) -> str:
    return f"tl_{_hash(f'{source_table_id}.{target_table_id}.{step_name}')}"


def quality_rule_id(job_id: str, rule_name: str) -> str:
    return f"qr_{_hash(f'{job_id}.{rule_name}')}"


def flag_id(ref_id: str, reason: str) -> str:
    return f"flg_{_hash(f'{ref_id}.{reason}')}"
