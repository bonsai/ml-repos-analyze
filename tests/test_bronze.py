import pandas as pd

from ml_repos_analyze.bronze import CONTRACT, repositories_to_bronze


def test_maps_raw_repositories_onto_contract():
    raw = pd.DataFrame(
        [
            {
                "full_name": "bonsai/workspace",
                "collected_at": "2026-11-11T00:00:00Z",
                "language": "Markdown",
                "fork": False,
                "archived": False,
                "stars": 1,
                "forks": 0,
                "open_issues": 2,
                "size": 500,
            }
        ]
    )
    out = repositories_to_bronze(raw)
    assert list(out.columns) == CONTRACT
    row = out.iloc[0]
    assert row["full_name"] == "bonsai/workspace"
    assert row["snapshot_at"] == "2026-11-11T00:00:00Z"
    assert row["stars"] == 1 and row["open_issues"] == 2
    # derived features absent from the raw export -> 0 / False
    assert row["commits_30d"] == 0
    assert bool(row["ci"]) is False


def test_missing_input_columns_do_not_raise():
    raw = pd.DataFrame([{"full_name": "a/b"}])
    out = repositories_to_bronze(raw)
    assert list(out.columns) == CONTRACT
    assert out.iloc[0]["stars"] == 0
    assert bool(out.iloc[0]["archived"]) is False
