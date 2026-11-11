#!/usr/bin/env python3
"""Run the health + cluster core on a raw repositories export.

Pipeline: repositories.jsonl -> bronze (repo_features contract) -> health
scores -> KMeans cluster_id -> human-readable report.

Usage:
    python tools/run_health_cluster.py <repositories.jsonl> \
        --bronze-out data/bronze/repos.jsonl --out report.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ml_repos_analyze.bronze import MISSING_FEATURES, repositories_to_bronze  # noqa: E402
from ml_repos_analyze.cluster import cluster_health  # noqa: E402
from ml_repos_analyze.health import score_frame  # noqa: E402

AXES = ["activity", "maintenance", "quality", "community", "architecture", "dependency"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repositories_jsonl")
    ap.add_argument("--bronze-out", default=None, help="write the bronze JSONL here")
    ap.add_argument("--clusters", type=int, default=8)
    ap.add_argument("--out", default=None, help="write the Markdown report here")
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()

    raw = pd.read_json(args.repositories_jsonl, lines=True)
    bronze = repositories_to_bronze(raw)

    if args.bronze_out:
        bp = Path(args.bronze_out)
        bp.parent.mkdir(parents=True, exist_ok=True)
        bronze.to_json(bp, orient="records", lines=True, force_ascii=False, date_format="iso")

    scored = score_frame(bronze)
    out = cluster_health(scored, n_clusters=args.clusters)

    lines = ["# repos health + cluster (real data)", ""]
    lines.append(f"source: `{args.repositories_jsonl}`")
    lines.append(f"rows: {len(out)}  |  clusters: {args.clusters}")
    lines.append("")
    lines.append(f"missing derived features (filled 0/False): {len(MISSING_FEATURES)}")
    lines.append(f"  {', '.join(MISSING_FEATURES)}")
    lines.append("")

    lines.append("## status")
    for k, v in out["status"].value_counts().items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## layer")
    for k, v in out["layer"].value_counts().items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## cluster_id")
    for k, v in out["cluster_id"].value_counts().sort_index().items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## axis summary (mean over rows)")
    for c in AXES + ["overall"]:
        lines.append(f"- {c}: {out[c].mean():.2f}")
    lines.append("")

    lines.append(f"## top {args.top} by overall")
    cols = ["full_name", "overall", "status", "layer", "cluster_id", "stars", "size"]
    for _, r in out.sort_values("overall", ascending=False).head(args.top).iterrows():
        lines.append(
            f"- {r['full_name']} | overall {r['overall']} | {r['status']} | "
            f"{r['layer']} | cluster {r['cluster_id']} | ★{r['stars']} | {r['size']}KB"
        )
    lines.append("")

    report = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    print(report)
    if args.out:
        print(f"[report written to {args.out}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
