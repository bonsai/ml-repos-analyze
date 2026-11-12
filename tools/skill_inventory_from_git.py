#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Restore the skill inventory time series from git history (Step 5 of the file
evolution plan, wiki #396).

Time points recovered (no new collection needed):

- 12a90e1 (2026-10-31)  operations/skills-inventory.json  — 555 entries
- 39b609d (2026-10-31)  operations/skills-inventory.json  — slightly different state
- 6999dba (2026-11-06)  operations/skills-inventory.json  (= 5f6bd71, identical)
- (untracked) operations/bqml/skills.ndjson — richer schema, exported_at 2026-11-09

skills/INDEX.yaml (same 2 commits) is skipped: name+category is a subset of
skills-inventory.json. One row per (skill, captured_at).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace") if hasattr(sys.stdout, "reconfigure") else None

GIT_SOURCES = [  # (path, commit)
    ("operations/skills-inventory.json", "12a90e1"),
    ("operations/skills-inventory.json", "39b609d"),
    ("operations/skills-inventory.json", "6999dba"),
]
NDJSON_SOURCE = "operations/bqml/skills.ndjson"  # untracked; dated by exported_at


def git_show(ws: Path, ref: str, path: str):
    p = subprocess.run(["git", "-C", str(ws), "show", f"{ref}:{path}"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return p.stdout if p.returncode == 0 else None


def commit_date(ws: Path, ref: str):
    p = subprocess.run(["git", "-C", str(ws), "show", "-s", "--format=%ad",
                        "--date=iso-strict", ref],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return p.stdout.strip() if p.returncode == 0 else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=str(Path.home() / "Documents/MEGA/WORKSPACE"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    ws = Path(args.workspace)

    rows: list[dict] = []
    seen: set[tuple] = set()
    summary: list[str] = []

    for path, ref in GIT_SOURCES:
        raw = git_show(ws, ref, path)
        if raw is None:
            summary.append(f"{ref}:{path} — not in history, skipped")
            continue
        date = commit_date(ws, ref)
        entries = json.loads(raw)
        added = 0
        for e in entries:
            row = {"captured_at": date, "commit": ref, "source": f"git:{path}@{ref}",
                   "skill": e.get("name"), "kind": e.get("kind"),
                   "category": e.get("category"), "desc": e.get("desc"),
                   "git_remote": e.get("git")}
            key = (row["captured_at"], row["source"], row["skill"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
            added += 1
        summary.append(f"{ref} ({date}): {len(entries)} entries, +{added} rows")

    nd = ws / NDJSON_SOURCE
    if nd.exists():
        added = 0
        with nd.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                e = json.loads(line)
                row = {"captured_at": e.get("exported_at"),
                       "commit": None, "source": f"file:{NDJSON_SOURCE}",
                       "skill": e.get("skill_name"), "kind": None,
                       "category": e.get("category"), "desc": e.get("description"),
                       "size_bytes": e.get("size_bytes"), "path": e.get("path")}
                key = (row["captured_at"], row["source"], row["skill"])
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
                added += 1
        summary.append(f"{NDJSON_SOURCE} (untracked): +{added} rows")

    rows.sort(key=lambda r: (r.get("captured_at") or "", r.get("source") or "", r.get("skill") or ""))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    per_point: dict = {}
    for r in rows:
        per_point.setdefault((r["captured_at"], r["source"]), set()).add(r["skill"])
    log_lines = [f"skill_inventory: {len(rows)} rows -> {out}"]
    log_lines += ["  " + s for s in summary]
    for (cap, src), sk in sorted(per_point.items()):
        log_lines.append(f"  {cap} {src}: {len(sk)} skills")
    report = "\n".join(log_lines)
    print(report)
    Path(str(out) + ".summary.txt").write_text(report + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
