#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bootstrap repo_snapshots.jsonl from the existing repositories export (Step 0 of
the file evolution plan, wiki #396).

One line = one repository at one point in time. Key = (full_name, captured_at).
Idempotent: re-running adds only rows whose key is not present yet.

Usage:
    python snapshots_from_repositories.py <repositories.jsonl> --out <repo_snapshots.jsonl>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# fields carried into the snapshot layer (superset of the #396 minimum:
# created_at / language / fork / archived are needed by predictions P1-P10)
FIELDS = [
    "full_name", "created_at", "updated_at", "pushed_at", "language",
    "fork", "archived", "stars", "forks", "open_issues", "size",
    "default_branch", "license", "topics", "description", "homepage",
    "collected_at",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repositories_jsonl")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.repositories_jsonl, encoding="utf-8") if l.strip()]
    out = Path(args.out)
    existing: list[dict] = []
    if out.exists():
        existing = [json.loads(l) for l in out.open(encoding="utf-8") if l.strip()]
    seen = {(r.get("full_name"), r.get("captured_at")) for r in existing}

    added = 0
    for r in rows:
        snap = {k: r.get(k) for k in FIELDS}
        snap["captured_at"] = r.get("collected_at")
        snap["source"] = "repositories.jsonl v1"
        key = (snap["full_name"], snap["captured_at"])
        if key in seen:
            continue
        existing.append(snap)
        seen.add(key)
        added += 1

    existing.sort(key=lambda r: (r.get("captured_at") or "", r.get("full_name") or ""))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for r in existing:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"repo_snapshots: {len(existing)} rows (+{added} added) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
