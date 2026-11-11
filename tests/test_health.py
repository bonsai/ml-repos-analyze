from ml_repos_analyze.health import score_row, score_frame
from ml_repos_analyze.cluster import cluster_health
import pandas as pd


def test_score_active_repo():
    r = score_row(
        {
            "full_name": "bonsai/ml-repos-analyze",
            "commits_30d": 25,
            "prs_merged_90d": 6,
            "releases_90d": 1,
            "ci": True,
            "tests": True,
            "stars": 3,
        }
    )
    assert r["status"] == "active"
    assert r["overall"] > 0
    assert r["layer"] == "ai/ml"


def test_cluster_runs():
    df = pd.DataFrame(
        [
            {"full_name": "a/ml-x", "commits_30d": 30, "stars": 10, "size": 100},
            {"full_name": "b/old", "commits_30d": 0, "stars": 0, "size": 10},
            {"full_name": "c/agent-y", "commits_30d": 5, "stars": 2, "size": 50},
        ]
    )
    scored = score_frame(df)
    clustered = cluster_health(scored, n_clusters=2)
    assert "cluster_id" in clustered.columns
    assert len(clustered) == 3
