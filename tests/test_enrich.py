import pandas as pd

from ml_repos_analyze.enrich import (
    apply_features,
    apply_proxy,
    proxy_commits,
    root_signals,
)


def _bronze():
    return pd.DataFrame(
        [
            {"full_name": "bonsai/a-repo", "commits_30d": 0.0, "ci": False,
             "tests": False, "lint": False, "package_count": 0.0},
            {"full_name": "bonsai/b-repo", "commits_30d": 0.0, "ci": False,
             "tests": False, "lint": False, "package_count": 0.0},
        ]
    )


def test_proxy_commits_buckets():
    assert proxy_commits(0) == 30
    assert proxy_commits(7) == 30
    assert proxy_commits(10) == 15
    assert proxy_commits(20) == 8
    assert proxy_commits(60) == 2
    assert proxy_commits(400) == 0
    assert proxy_commits(None) == 0


def test_root_signals():
    root = [
        {"name": "pyproject.toml", "type": "blob"},
        {"name": "README.md", "type": "blob"},
        {"name": "tests", "type": "tree"},
        {"name": ".eslintrc.yml", "type": "blob"},
    ]
    s = root_signals(root, [{"name": "ci.yml"}])
    assert s["ci"] is True
    assert s["tests"] is True
    assert s["lint"] is True
    assert s["documentation"] is True
    assert s["package_count"] == 1
    empty = root_signals([{"name": "main.py", "type": "blob"}], [])
    assert empty["ci"] is False and empty["tests"] is False


def test_apply_features_traces_source():
    bronze = _bronze()
    feats = {
        "bonsai/a-repo": {"commits_30d": 12, "ci": True, "tests": True,
                          "lint": False, "package_count": 1},
    }
    out = apply_features(bronze, feats)
    assert out.loc[0, "commits_30d"] == 12.0
    assert bool(out.loc[0, "ci"]) is True
    assert out.loc[0, "feature_source"] == "api"
    assert out.loc[1, "feature_source"] == "none"
    assert out.loc[1, "commits_30d"] == 0.0


def test_apply_proxy_fills_only_non_api_rows():
    bronze = _bronze()
    bronze["feature_source"] = ["api", "none"]
    pushed = pd.Series(
        [pd.Timestamp("2026-11-12", tz="UTC"), pd.Timestamp("2026-10-01", tz="UTC")],
        index=bronze.index,
    )
    now = pd.Timestamp("2026-11-12", tz="UTC")
    out, applied = apply_proxy(bronze, pushed, now=now.to_pydatetime())
    assert applied == 1  # only the non-api row is processed
    # the api row keeps its collected value even though it was pushed today
    assert out.loc[0, "feature_source"] == "api"
    assert out.loc[0, "commits_30d"] == 0.0
    # 2026-10-01 is 42 days before 2026-11-12 -> bucket (90, 2)
    assert out.loc[1, "feature_source"] == "proxy"
    assert out.loc[1, "commits_30d"] == 2.0
