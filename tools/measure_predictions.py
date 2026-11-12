#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Measure the pre-registered predictions P1-P10 (ml-repos-analyze
docs/file-evolution-plan.md §3) against repo_snapshots.jsonl.

kaggle-prediction phase 2: predictions were registered BEFORE measurement
(commit a332710); this script fills the §5 table. Read-only.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from re import split as resplit

sys.stdout.reconfigure(errors="replace") if hasattr(sys.stdout, "reconfigure") else None


def parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def judge(measured, lo, hi):
    if measured is None:
        return "n/a"
    if lo <= measured <= hi:
        return "✅ 範囲内"
    return f"⚠️ 外れ（{'上' if measured > hi else '下'}）"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshots")
    ap.add_argument("--out", default=None)
    ap.add_argument("--as-of", default=None, help="ISO datetime for 'today'")
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.snapshots, encoding="utf-8") if l.strip()]
    latest: dict = {}
    for r in rows:
        k = r.get("full_name")
        if k and (k not in latest or (r.get("captured_at") or "") > (latest[k].get("captured_at") or "")):
            latest[k] = r
    repos = list(latest.values())
    now = parse_dt(args.as_of) or datetime.now(timezone.utc)

    for r in repos:
        r["_created"] = parse_dt(r.get("created_at"))
        r["_pushed"] = parse_dt(r.get("pushed_at"))
        r["_age"] = max((now - r["_created"]).days, 0) if r["_created"] else None
        r["_recency"] = max((now - r["_pushed"]).days, 0) if r["_pushed"] else None

    own = [r for r in repos if not r.get("fork")]
    forks = [r for r in repos if r.get("fork")]
    own_active = [r for r in own if not r.get("archived")]

    lines = ["# repo metadata measurements — P1〜P10 照合（wiki #396 §5）", ""]
    fork_and_arch = sum(1 for r in repos if r.get("fork") and r.get("archived"))
    own_arch = sum(1 for r in repos if not r.get("fork") and r.get("archived"))
    lines.append(f"as-of: {now.isoformat()} / snapshots: {len(rows)} rows / repos: {len(repos)} "
                 f"(fork {len(forks)} / own {len(own)} = own_active {len(own_active)} + own_archived {own_arch}; fork∧archived {fork_and_arch})")
    lines.append("")

    # ---- P1 誕生バースト -------------------------------------------------
    months = Counter(r["_created"].strftime("%Y-%m") for r in repos if r["_created"])
    nonzero = [c for c in months.values() if c > 0]
    med = statistics.median(nonzero) if nonzero else 0
    spikes = [m for m, c in months.items() if med and c >= 3 * med]
    max_month, max_cnt = (months.most_common(1)[0] if months else (None, 0))
    max_share = max_cnt / len(repos)
    lines.append("## P1 誕生の時間構造")
    lines.append(f"- 月次 top5: {[(m, c) for m, c in months.most_common(5)]}")
    lines.append(f"- スパイク月（≥3×中央値）: {len(spikes)} 件 {sorted(spikes)[:6]}")
    lines.append(f"- 最大月シェア: {100*max_share:.1f}%（{max_month}）")
    lines.append("")

    # ---- P2 年齢 ----------------------------------------------------------
    ages = sorted(r["_age"] for r in repos if r["_age"] is not None)
    med_age = statistics.median(ages) if ages else None
    lines.append("## P2 年齢")
    lines.append(f"- 年齢中央値: {med_age} 日（min {ages[0] if ages else '-'} / max {ages[-1] if ages else '-'}）")
    lines.append("")

    # ---- P3 言語 ----------------------------------------------------------
    langs = Counter((r.get("language") or "(null)") for r in repos)
    top_langs = langs.most_common(8)
    py = 100 * langs.get("Python", 0) / len(repos)
    jsts = 100 * (langs.get("JavaScript", 0) + langs.get("TypeScript", 0)) / len(repos)
    null = 100 * langs.get("(null)", 0) / len(repos)
    lines.append("## P3 言語")
    lines.append(f"- top: {top_langs}")
    lines.append(f"- Python {py:.1f}% / JS+TS {jsts:.1f}% / null {null:.1f}%")
    lines.append("")

    # ---- P4 サイズ集中 ----------------------------------------------------
    sized = sorted((r for r in repos if (r.get("size") or 0) > 0), key=lambda r: r["size"], reverse=True)
    total_size = sum(r.get("size") or 0 for r in repos)
    top10 = sized[:10]
    top10_share = 100 * sum(r["size"] for r in top10) / total_size if total_size else 0
    lines.append("## P4 サイズ集中")
    lines.append(f"- top10 シェア: {top10_share:.1f}%（total {total_size:,} KB）")
    lines.append(f"- top10: {[(r['full_name'], r['size']) for r in top10]}")
    lines.append("")

    # ---- P5/P6 完全性 -----------------------------------------------------
    def rate(pred):
        return 100 * sum(1 for r in repos if pred(r)) / len(repos)

    topics_rate = rate(lambda r: bool(r.get("topics")))
    lic_rate = rate(lambda r: bool(r.get("license")))
    home_rate = rate(lambda r: bool(r.get("homepage")))
    desc_rate = rate(lambda r: bool(r.get("description")))
    lines.append("## P5/P6 完全性")
    lines.append(f"- topics {topics_rate:.1f}% / license {lic_rate:.1f}% / homepage {home_rate:.1f}% / description {desc_rate:.1f}%")
    lines.append("")

    # ---- P7/P8 recency ----------------------------------------------------
    def fresh(rs, days):
        vals = [r["_recency"] for r in rs if r["_recency"] is not None]
        return 100 * sum(1 for v in vals if v <= days) / len(vals) if vals else 0

    fork_fresh = fresh(forks, 90)
    own_fresh90 = fresh(own_active, 90)
    own_fresh365 = fresh(own_active, 365)
    lines.append("## P7/P8 recency")
    lines.append(f"- fork の 90 日以内 push 率: {fork_fresh:.1f}%（n={len(forks)}）")
    lines.append(f"- own（非 fork・非 archived）の 90 日以内 push 率: {own_fresh90:.1f}%（n={len(own_active)}）")
    lines.append(f"- own の 365 日以内 push 率: {own_fresh365:.1f}%")
    lines.append("")

    # ---- P9 big & dead ----------------------------------------------------
    big_dead = [r for r in sized[:20] if (r["_recency"] is not None and r["_recency"] >= 365)]
    lines.append("## P9 big & dead（size top20 ∧ 365 日以上 push なし）")
    lines.append(f"- 件数: {len(big_dead)} / 20")
    for r in big_dead[:10]:
        lines.append(f"  - {r['full_name']} — {r['size']:,} KB, last push {r['_pushed'].date() if r['_pushed'] else '?'}")
    lines.append("")

    # ---- P10 名前空間 -----------------------------------------------------
    toks = Counter()
    for r in repos:
        name = (r.get("full_name") or "").split("/")[-1]
        first = resplit(r"[-_.]", name)[0].lower() if name else ""
        if first:
            toks[first] += 1
    clusters = [t for t, c in toks.items() if c >= 5]
    lines.append("## P10 名前空間クラスタ（先頭トークン ≥5 repo）")
    lines.append(f"- クラスタ数: {len(clusters)} / tokens: {sorted((t, c) for t, c in toks.items() if c >= 5)}")
    lines.append("")

    # ---- 予測 vs 実測 -----------------------------------------------------
    lines.append("## 予測 vs 実測（docs/file-evolution-plan.md §5 を埋める）")
    lines.append("")
    lines.append("| # | 予測 | 実測 | 判定 |")
    lines.append("|---|---|---|---|")
    lines.append(f"| P1 | スパイク ≥3、最大月 >15% | スパイク {len(spikes)}、最大 {100*max_share:.1f}% | {judge(len(spikes), 3, 10**9)} ／ {judge(round(100*max_share), 16, 10**9)} |")
    lines.append(f"| P2 | 中央値 180〜400 日 | {med_age} 日 | {judge(med_age, 180, 400)} |")
    lines.append(f"| P3 | Python 35〜50% / JS-TS 20〜35% / null 10〜25% | {py:.0f}% / {jsts:.0f}% / {null:.0f}% | {judge(round(py), 35, 50)} / {judge(round(jsts), 20, 35)} / {judge(round(null), 10, 25)} |")
    lines.append(f"| P4 | top10 >60% | {top10_share:.0f}% | {judge(round(top10_share), 61, 10**9)} |")
    lines.append(f"| P5 | topics <20% | {topics_rate:.0f}% | {judge(round(topics_rate), 0, 19)} |")
    lines.append(f"| P6 | license <30% / homepage <20% / desc 50〜80% | {lic_rate:.0f}% / {home_rate:.0f}% / {desc_rate:.0f}% | {judge(round(lic_rate), 0, 29)} / {judge(round(home_rate), 0, 19)} / {judge(round(desc_rate), 50, 80)} |")
    lines.append(f"| P7 | fork 鮮度 > own 鮮度（90d） | fork {fork_fresh:.0f}% vs own {own_fresh90:.0f}% | {'✅ 予測どおり' if fork_fresh > own_fresh90 else '⚠️ 外れ'} |")
    lines.append(f"| P8 | own 90 日以内 push 15〜25% | {own_fresh90:.0f}% | {judge(round(own_fresh90), 15, 25)} |")
    lines.append(f"| P9 | big&dead 過半（≥10/20） | {len(big_dead)}/20 | {judge(len(big_dead), 10, 20)} |")
    lines.append(f"| P10 | クラスタ 8〜12 | {len(clusters)} | {judge(len(clusters), 8, 12)} |")
    lines.append("")
    lines.append("P11（file churn）/ P12（消失検出）は file_manifests の 2 時点目以降に測定可能になる。")

    report = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    if args.out:
        print(f"[report written to {args.out}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
