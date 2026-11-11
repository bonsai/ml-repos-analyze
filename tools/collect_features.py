#!/usr/bin/env python3
"""Collect activity features for a repositories export via GitHub GraphQL.

Reads a repositories.jsonl (raw GitHub metadata), optionally filters out
forks / archived repos, and collects per-repo features in batched GraphQL
queries (~40 repos per request):

- commits_30d  (default-branch history in the last 30 days)
- ci / tests / lint / documentation / package_count (tree heuristics)

Writes a JSON dict {full_name: {...} | null} for tools/run_health_cluster.py
(--features). Missing derived features (prs_merged_90d, coverage, loc, ...)
have no GraphQL source and stay with the proxy/zero handling.

Usage:
    python tools/collect_features.py <repositories.jsonl> \
        --out data/bronze/features_api.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ml_repos_analyze.enrich import collect_features  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repositories_jsonl")
    ap.add_argument("--out", default="data/bronze/features_api.json")
    ap.add_argument("--since", default=None, help="ISO timestamp (default: now-30d)")
    ap.add_argument("--batch-size", type=int, default=40)
    ap.add_argument("--include-forks", action="store_true")
    ap.add_argument("--include-archived", action="store_true")
    args = ap.parse_args()

    raw = pd.read_json(args.repositories_jsonl, lines=True)
    mask = pd.Series(True, index=raw.index)
    if not args.include_forks:
        mask &= ~raw["fork"].fillna(False).astype(bool)
    if not args.include_archived:
        mask &= ~raw["archived"].fillna(False).astype(bool)
    targets = raw.loc[mask, "full_name"].tolist()
    skipped = len(raw) - len(targets)

    def log(msg: str) -> None:
        print(msg, flush=True)

    feats = collect_features(
        targets, since=args.since, batch_size=args.batch_size, log=log
    )
    found = {k: v for k, v in feats.items() if v}
    missing = [k for k, v in feats.items() if not v]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"collected: {len(found)} / {len(targets)} targets "
          f"(skipped fork/archived: {skipped}, unreadable: {len(missing)})")
    if missing:
        print("unreadable repos: " + ", ".join(missing[:10]) +
              (" ..." if len(missing) > 10 else ""))
    print(f"[features written to {out}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
