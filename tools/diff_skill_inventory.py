#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diff the skill inventory time series (skill_inventory.jsonl, wiki #396).

For each adjacent pair of time points: which skills appeared / disappeared.
Cross-source transitions are flagged (schema/scope may differ, so counts are
indicative rather than exact).

Usage:
    diff_skill_inventory.py <skill_inventory.jsonl> [--out report.md]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(errors="replace") if hasattr(sys.stdout, "reconfigure") else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inventory")
    ap.add_argument("--out", default=None)
    ap.add_argument("--examples", type=int, default=10)
    args = ap.parse_args()

    points: dict[tuple, set] = defaultdict(set)
    with open(args.inventory, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            key = (r.get("captured_at") or "", r.get("source") or "")
            if r.get("skill"):
                points[key].add(r["skill"])

    order = sorted(points.keys())
    lines = ["# skill inventory diff — 時点間の増減（wiki #396 分析層）", ""]
    lines.append(f"time points: {len(order)}")
    for (cap, src), skills in sorted(points.items()):
        lines.append(f"- {cap} | {src} | {len(skills)} skills")
    lines.append("")

    for prev, curr in zip(order, order[1:]):
        same_source = prev[1] == curr[1]
        added = sorted(points[curr] - points[prev])
        removed = sorted(points[prev] - points[curr])
        flag = "" if same_source else "（⚠️ source が変わる遷移 — 参考値）"
        lines.append(f"## {prev[0][:10]} → {curr[0][:10]} {flag}")
        lines.append(f"- added: **{len(added)}** / removed: **{len(removed)}** / "
                     f"net: {len(points[curr]) - len(points[prev]):+d}")
        if added:
            lines.append(f"- added examples: {', '.join(added[:args.examples])}"
                         f"{' …' if len(added) > args.examples else ''}")
        if removed:
            lines.append(f"- removed examples: {', '.join(removed[:args.examples])}"
                         f"{' …' if len(removed) > args.examples else ''}")
        lines.append("")

    report = "\n".join(lines) + "\n"
    print(report)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"[report written to {args.out}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
