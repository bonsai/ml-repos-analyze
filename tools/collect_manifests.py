#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Capture per-repo file manifests (Step 1 of the file evolution plan, wiki #396).

For each repository (from repo_snapshots.jsonl, non-forks by default) run
    GET /repos/{owner}/{repo}/git/trees/HEAD?recursive=1
and emit one JSONL row per blob file:

    {full_name, path, size, blob_sha, captured_at, truncated}

Empty repositories are recorded as a single row with path=null. API errors
(404 renamed/deleted, 409 empty, ...) go to a sidecar errors file instead —
a repo-level disappearance is data for P12 (消失検出), not noise.

Write to a LOCAL path first; copy to Drive after the run finishes
(many small writes to a cloud mount are slow and fragile).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(errors="replace") if hasattr(sys.stdout, "reconfigure") else None


def gh_api(url: str, gh: str = "gh", timeout: float = 60.0):
    """Return (parsed_json_or_None, error_string_or_None)."""
    last = ""
    for attempt in range(3):
        proc = subprocess.run([gh, "api", url], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
        if proc.returncode == 0 and proc.stdout.strip():
            try:
                return json.loads(proc.stdout), None
            except json.JSONDecodeError:
                last = "json decode error"
        else:
            last = proc.stderr.strip()[:200]
        if any(k in last for k in ("404", "409", "Not Found", "Git repository is empty")):
            return None, last
        time.sleep(2 * (attempt + 1))
    return None, last


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshots")
    ap.add_argument("--out", required=True, help="local output jsonl (copy to Drive after)")
    ap.add_argument("--errors", default=None, help="sidecar jsonl for API errors")
    ap.add_argument("--include-forks", action="store_true")
    ap.add_argument("--gh", default="gh")
    ap.add_argument("--min-rate", type=int, default=150)
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.snapshots, encoding="utf-8") if l.strip()]
    latest: dict = {}
    for r in rows:
        k = r.get("full_name")
        if k and (k not in latest or (r.get("captured_at") or "") > (latest[k].get("captured_at") or "")):
            latest[k] = r
    names = sorted(k for k, r in latest.items() if args.include_forks or not r.get("fork"))
    captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    err_path = Path(args.errors) if args.errors else out.with_suffix(".errors.jsonl")

    files_total = 0
    repos_ok = repos_empty = repos_error = truncated = 0

    def log(m):
        print(f"{datetime.now(timezone.utc).strftime('%H:%M:%S')} {m}", flush=True)

    log(f"targets: {len(names)} repos (include_forks={args.include_forks})")
    with out.open("w", encoding="utf-8") as fo, err_path.open("w", encoding="utf-8") as fe:
        for i, full in enumerate(names):
            if i and i % 50 == 0:
                rl, _ = gh_api("rate_limit", gh=args.gh)
                remaining = (rl or {}).get("resources", {}).get("core", {}).get("remaining", 0)
                log(f"  rate remaining: {remaining}")
                if remaining < args.min_rate:
                    log("rate limit low — stopping early (partial capture is still valid)")
                    break

            data, err = gh_api(f"repos/{full}/git/trees/HEAD?recursive=1", gh=args.gh)
            if data is None:
                repos_error += 1
                fe.write(json.dumps({"full_name": full, "captured_at": captured_at,
                                     "error": (err or "unknown")[:200]}, ensure_ascii=False) + "\n")
            else:
                tree = data.get("tree") or []
                trunc = bool(data.get("truncated"))
                truncated += 1 if trunc else 0
                if not tree:
                    repos_empty += 1
                    fo.write(json.dumps({"full_name": full, "path": None, "size": None,
                                         "blob_sha": None, "captured_at": captured_at,
                                         "truncated": False}, ensure_ascii=False) + "\n")
                else:
                    repos_ok += 1
                    for e in tree:
                        if e.get("type") != "blob":
                            continue
                        fo.write(json.dumps({"full_name": full, "path": e.get("path"),
                                             "size": e.get("size"), "blob_sha": e.get("sha"),
                                             "captured_at": captured_at,
                                             "truncated": trunc}, ensure_ascii=False) + "\n")
                        files_total += 1
            if (i + 1) % 25 == 0 or i == len(names) - 1:
                log(f"{i+1}/{len(names)} done — files so far {files_total}, "
                    f"errors {repos_error}, empty {repos_empty}")

    log(f"summary: repos ok={repos_ok} empty={repos_empty} error={repos_error} "
        f"truncated={truncated} files={files_total} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
