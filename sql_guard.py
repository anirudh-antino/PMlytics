"""
Read-only SQL gatekeeper for PM-facing natural language analytics.
"""

from __future__ import annotations

import re

FORBIDDEN_PATTERN = re.compile(
    r"\b("
    r"insert|update|delete|merge|truncate|drop|alter|create|replace|grant|revoke|"
    r"attach|detach|vacuum|analyze\s+database|call|execute|exec\b|"
    r"into\s+outfile|into\s+dumpfile|copy\s*\(|load_file|benchmark|pg_sleep|"
    r"waitfor\s+delay|shutdown"
    r")\b",
    re.IGNORECASE | re.DOTALL,
)


def strip_sql_comments(sql: str) -> str:
    s = sql.strip()
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.DOTALL)
    lines = []
    for line in s.splitlines():
        if "--" in line:
            line = line.split("--", 1)[0]
        lines.append(line)
    return " ".join(lines)


def validate_select_only(sql: str) -> tuple[bool, str]:
    if not sql or not sql.strip():
        return False, "Empty SQL."

    cleaned = strip_sql_comments(sql).strip().rstrip(";")

    if ";" in cleaned:
        return False, "Only one SQL statement is allowed."

    lower = cleaned.lstrip().lower()
    if not lower.startswith("select") and not lower.startswith("with"):
        return False, "Only SELECT / WITH … SELECT queries are allowed."

    if FORBIDDEN_PATTERN.search(cleaned):
        return False, "That SQL pattern is blocked for safety."

    return True, cleaned


def enforce_limit(sql: str, dialect: str, max_rows: int) -> str:
    """Append LIMIT if absent (best-effort per dialect)."""
    cleaned = sql.strip().rstrip(";")
    lim = max_rows
    low = cleaned.lower()

    if dialect == "mysql":
        if re.search(r"\blimit\s+\d+\s*$", low):
            return cleaned
        return f"{cleaned} LIMIT {lim}"

    if dialect in ("postgresql", "sqlite", "generic"):
        if re.search(r"\blimit\s+\d+\s*$", low):
            return cleaned
        return f"{cleaned} LIMIT {lim}"

    if "limit" in low.split("offset")[0]:
        return cleaned
    return f"{cleaned} LIMIT {lim}"
