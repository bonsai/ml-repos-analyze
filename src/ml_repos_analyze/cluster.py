"""sklearn KMeans stand-in for BQML repo health clustering."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

FEATURE_COLS = [
    "activity",
    "maintenance",
    "quality",
    "community",
    "architecture",
    "dependency",
]


def cluster_health(
    scored: pd.DataFrame,
    n_clusters: int = 8,
    random_state: int = 42,
) -> pd.DataFrame:
    """Attach cluster_id using health axes + log size/stars/forks."""
    out = scored.copy()
    for c in FEATURE_COLS:
        if c not in out.columns:
            out[c] = 0.0

    X = out[FEATURE_COLS].astype(float).fillna(0.0)
    X["log_size"] = np.log1p(out.get("size", 0).fillna(0).astype(float))
    X["log_stars"] = np.log1p(out.get("stars", 0).fillna(0).astype(float))
    X["log_forks"] = np.log1p(out.get("forks", 0).fillna(0).astype(float))
    X["is_fork"] = out.get("fork", False).fillna(False).astype(int)

    Xs = StandardScaler().fit_transform(X.values)
    n = min(n_clusters, max(1, len(out)))
    labels = KMeans(n_clusters=n, n_init=10, random_state=random_state).fit_predict(Xs)
    out["cluster_id"] = labels
    return out
