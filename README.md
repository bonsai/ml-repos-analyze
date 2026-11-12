# ml-repos-analyze

**Kaggle-first rebuild** of [bonsai/repos-analyze](https://github.com/bonsai/repos-analyze).

| | repos-analyze (legacy) | ml-repos-analyze (this) |
|---|---|---|
| Primary runtime | BigQuery / local DuckDB | **Kaggle notebooks + sklearn** |
| Scoring | SQL `calculate_all_repo_health.sql` | `src/.../health.py` (same formulas) |
| Clustering | BQML KMEANS | sklearn KMeans (local_cluster equivalent) |
| Data contract | JSONL / BQ tables | bronze JSONL (kaggle-bqml-core style) |
| Goal | Full observatory + actions | **Portable ML core** you can run free |

**Rename note**: GitHub rename of `repos-analyze` → `ml-repos-analyze` is not done via API here.  
This repo is the new ML-oriented line. Keep `repos-analyze` as the operational observatory until you rename/archive it in the UI.

**Author**: Scaffold + port by Grok (xAI) — 2026-11-11

---

## Layout (template-applied)

```
.
├── schema/repo_features.yaml     # feature contract
├── src/ml_repos_analyze/
│   ├── health.py                 # deterministic scores (from BQML SQL)
│   ├── cluster.py                # sklearn KMeans
│   └── io.py                     # bronze JSONL
├── notebooks/
│   └── 01_kaggle_health_cluster.ipynb
├── data/bronze/                  # sample or your export
├── tests/
└── .github/workflows/ci.yml
```

---

## Health score (ported)

Same axes as `bqml/calculate_all_repo_health.sql`:

- **activity** — commits_30d, prs, issues flow
- **maintenance** — activity + releases
- **quality** — tests, coverage, CI, docs
- **community** — contributors, stars, forks
- **architecture** — modules, network
- **dependency** — package / dependency signals
- **overall** — mean of the six
- **status** — active / maintained / dormant / archived / fork
- **layer** — agent/workflow, ai/ml, content, interface, data/knowledge, software

Missing columns are treated as 0 / False so a minimal GitHub export still runs.

---

## Quick start on Kaggle

1. Upload this repo (or `src/` + `schema/`) as a Dataset
2. Open `notebooks/01_kaggle_health_cluster.ipynb`
3. Point at bronze JSONL of repo snapshots (or the tiny sample)
4. Run health → cluster → inspect

Later: same features feed real BQML `CREATE MODEL` in `repos-analyze`.

**Phase 2 (file evolution plan)**: see [docs/file-evolution-plan.md](./docs/file-evolution-plan.md) — track file/repo evolution across all repos via GH metadata (repo_snapshots / file_manifests / events), with pre-registered predictions P1–P12.
