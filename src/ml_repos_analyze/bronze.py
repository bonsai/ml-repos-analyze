"""Bronze adapter: raw GitHub repository rows -> repo_features contract.

The health core (health.py) is written against schema/repo_features.yaml,
which mixes raw GitHub metadata with *derived* activity/quality features
(commits_30d, prs_merged_90d, coverage, ...). A plain GitHub `repositories`
export (transform of `gh api users/<owner>/repos`) only carries the raw
half, so those derived features are absent here.

Missing features are filled with 0 / False, exactly as health.py documents
("Missing columns are treated as 0 / False so a minimal GitHub export still
runs"). This module does not invent values; enrichment is a separate,
explicit step.
"""

from __future__ import annotations

import pandas as pd

# Column order mirrors schema/repo_features.yaml.
CONTRACT = [
    "full_name", "snapshot_at", "fork", "archived", "language",
    "stars", "forks", "size", "open_issues",
    "commits_30d", "prs_merged_90d", "releases_90d",
    "contributors_90d", "contributors_total", "issues_closed_90d",
    "test_loc", "loc", "coverage",
    "ci", "tests", "lint", "security_scan", "documentation",
    "package_count", "module_count", "dependency_count",
    "incoming", "outgoing",
]

BOOL_COLS = {"fork", "archived", "ci", "tests", "lint", "security_scan"}
STRING_COLS = {"full_name", "snapshot_at", "language"}

# Derived features this adapter cannot supply (documented for the report).
MISSING_FEATURES = [c for c in CONTRACT if c not in
                    {"full_name", "snapshot_at", "fork", "archived", "language",
                     "stars", "forks", "size", "open_issues"}]


def repositories_to_bronze(df: pd.DataFrame) -> pd.DataFrame:
    """Map a raw repositories frame onto the repo_features contract.

    Reads `collected_at` (falling back to `updated_at`) as `snapshot_at`.
    Every column not present in the input becomes 0 (numeric) or False
    (boolean).
    """
    df = df.copy()
    if "snapshot_at" not in df.columns:
        if "collected_at" in df.columns:
            df["snapshot_at"] = df["collected_at"]
        elif "updated_at" in df.columns:
            df["snapshot_at"] = df["updated_at"]

    out = pd.DataFrame(index=df.index)
    for col in CONTRACT:
        if col in df.columns:
            s = df[col]
        else:
            s = pd.Series([None] * len(df), index=df.index)
        if col in BOOL_COLS:
            out[col] = s.fillna(False).astype(bool)
        elif col in STRING_COLS:
            out[col] = s
        else:
            out[col] = pd.to_numeric(s, errors="coerce").fillna(0)
    return out
