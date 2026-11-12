#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diff two file-manifest captures into events.jsonl (Step 2 of the file
evolution plan, wiki #396).

Events:
    repo_added / repo_vanished        (repo level — P12 消失検出)
    file_added / file_removed / file_changed (file level — P11 churn)

A repo whose manifests are identical produces zero events. Truncated
manifests are flagged in the summary (their diffs overstate removals).

Usage:
    diff_manifests.py OLD.jsonl NEW.jsonl --out events.jsonl [--summary report.md]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(errors="replace") if hasattr(sys.stdout, "reconfigure") else None


def load(path: str):
    repos: dict[str, dict[str, tuple]] = defaultdict(dict)
    truncated: set[str] = set()
    captured = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            full = r.get("full_name")
            if not full:
                continue
            captured[full] = r.get("captured_at")
            if r.get("truncated"):
                truncated.add(full)
            p = r.get("path")
            if p is None:  # empty-repo marker
                repos.setdefault(full, {})
                continue
            repos[full][p] = (r.get("blob_sha"), r.get("size"))
    return repos, truncated, captured


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--out", required=True, help="events.jsonl")
    ap.add_argument("--summary", default=None)
    ap.add_argument("--detected-at", default=None)
    args = ap.parse_args()

    old, old_trunc, _ = load(args.old)
    new, new_trunc, _ = load(args.new)
    detected = args.detected_at or datetime.now(timezone.utc).isoformat(timespec="seconds")

    events: list[dict] = []

    for full in sorted(set(old) - set(new)):
        events.append({"event": "repo_vanished", "full_name": full,
                       "old_files": len(old[full]), "detected_at": detected})
    for full in sorted(set(new) - set(old)):
        events.append({"event": "repo_added", "full_name": full,
                       "new_files": len(new[full]), "detected_at": detected})

    churn: list[tuple[str, int, int]] = []
    files_added = files_removed = files_changed = 0
    for full in sorted(set(old) & set(new)):
        o, n = old[full], new[full]
        added = sorted(p for p in n if p not in o)
        removed = sorted(p for p in o if p not in n)
        changed = sorted(p for p in (o.keys() & n.keys()) if o[p][0] != n[p][0])
        for p in added:
            events.append({"event": "file_added", "full_name": full, "path": p,
                           "new_size": n[p][1], "detected_at": detected})
        for p in removed:
            events.append({"event": "file_removed", "full_name": full, "path": p,
                           "old_size": o[p][1], "detected_at": detected})
        for p in changed:
            events.append({"event": "file_changed", "full_name": full, "path": p,
                           "old_size": o[p][1], "new_size": n[p][1], "detected_at": detected})
        files_added += len(added)
        files_removed += len(removed)
        files_changed += len(changed)
        total = max(1, len(n))
        churn.append((full, len(added) + len(removed) + len(changed), total))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    lines = ["# manifest diff summary", ""]
    lines.append(f"old: {args.old} ({len(old)} repos) / new: {args.new} ({len(new)} repos)")
    lines.append(f"detected_at: {detected}")
    lines.append("")
    lines.append(f"- repo_added: {len(new) - len(set(old) & set(new))} / repo_vanished: {len(set(old) - set(new))}")
    lines.append(f"- file_added: {files_added} / file_removed: {files_removed} / file_changed: {files_changed}")
    total_new_files = sum(len(new[f]) for f in (set(old) & set(new)))
    overall = 100 * (files_added + files_removed + files_changed) / max(1, total_new_files)
    lines.append(f"- overall churn: {overall:.1f}%（events / new files、P11 の閾値は ≤20%）")
    suspect = sorted(old_trunc | new_trunc)
    if suspect:
        lines.append(f"- ⚠️ truncated manifests（diff の信頼性注意）: {', '.join(suspect)}")
    top = sorted(churn, key=lambda t: t[1], reverse=True)[:15]
    lines.append("- churn 上位 15（repo, events, files）:")
    for full, evs, tot in top:
        if evs:
            lines.append(f"  - {full}: {evs} events / {tot} files")
    lines.append("")

    summary = "\n".join(lines) + "\n"
    print(summary)
    if args.summary:
        Path(args.summary).write_text(summary, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
