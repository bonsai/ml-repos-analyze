"""Deterministic repo health scores — port of bqml/calculate_all_repo_health.sql."""

from __future__ import annotations

import math
import re
from typing import Any

import numpy as np
import pandas as pd


def _log1p(x: Any) -> float:
    try:
        v = float(x) if x is not None and not (isinstance(x, float) and math.isnan(x)) else 0.0
    except (TypeError, ValueError):
        v = 0.0
    return math.log1p(max(v, 0.0))


def _boolish(x: Any) -> bool:
    if isinstance(x, bool):
        return x
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return False
    if isinstance(x, (int, float)):
        return bool(x)
    return str(x).lower() in {"1", "true", "yes", "y"}


def _num(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def score_row(r: dict[str, Any]) -> dict[str, Any]:
    """Score one repository snapshot (same formulas as BQ SQL)."""
    commits_30d = _num(r.get("commits_30d"))
    prs_merged_90d = _num(r.get("prs_merged_90d"))
    releases_90d = _num(r.get("releases_90d"))
    contributors_90d = _num(r.get("contributors_90d"))
    issues_closed_90d = _num(r.get("issues_closed_90d"))
    test_loc = _num(r.get("test_loc"))
    loc = _num(r.get("loc"))
    coverage = _num(r.get("coverage"))
    documentation = _num(r.get("documentation"))
    package_count = _num(r.get("package_count"))
    module_count = _num(r.get("module_count"))
    dependency_count = _num(r.get("dependency_count"))
    incoming = _num(r.get("incoming"))
    outgoing = _num(r.get("outgoing"))
    contributors_total = _num(r.get("contributors_total"))
    stars = _num(r.get("stars"))
    forks = _num(r.get("forks"))
    size = _num(r.get("size"))
    fork = _boolish(r.get("fork"))
    archived = _boolish(r.get("archived"))
    ci = _boolish(r.get("ci"))
    tests = _boolish(r.get("tests"))
    lint = _boolish(r.get("lint"))
    security_scan = _boolish(r.get("security_scan"))

    activity_commit = min(100.0, 20.0 * _log1p(commits_30d))
    activity_delivery = min(100.0, 15.0 * _log1p(prs_merged_90d) + 10.0 * _log1p(releases_90d))
    community_activity = min(100.0, 25.0 * _log1p(contributors_90d))
    issue_flow = min(100.0, 20.0 * _log1p(issues_closed_90d))
    test_ratio_score = min(100.0, 100.0 * (test_loc / loc) if loc > 0 else 0.0)
    coverage_score = min(100.0, coverage)
    automation_score = (
        (35.0 if ci else 0.0)
        + (25.0 if tests else 0.0)
        + (20.0 if lint else 0.0)
        + (20.0 if security_scan else 0.0)
    )
    documentation_score = min(100.0, documentation)
    architecture_size_score = min(
        100.0,
        20.0 * _log1p(package_count)
        + 20.0 * _log1p(module_count)
        + 20.0 * _log1p(dependency_count),
    )
    network_score = min(
        100.0,
        20.0 * _log1p(incoming)
        + 20.0 * _log1p(outgoing)
        + 20.0 * _log1p(contributors_total),
    )

    activity = round((activity_commit + activity_delivery + issue_flow) / 3.0, 2)
    maintenance = round(
        (activity_commit + activity_delivery + issue_flow + (100.0 if releases_90d > 0 else 0.0)) / 4.0, 2
    )
    quality = round(
        (test_ratio_score + coverage_score + automation_score + documentation_score) / 4.0, 2
    )
    community = round(
        (
            community_activity
            + min(100.0, 20.0 * _log1p(stars))
            + min(100.0, 20.0 * _log1p(forks))
        )
        / 3.0,
        2,
    )
    architecture = round(
        (architecture_size_score + network_score + (100.0 if module_count > 0 else 0.0)) / 3.0, 2
    )
    dependency = round(
        (
            (100.0 if r.get("dependency_count") is not None else 0.0)
            + (100.0 if package_count > 0 else 0.0)
            + min(100.0, 20.0 * _log1p(dependency_count))
        )
        / 3.0,
        2,
    )
    overall = round((activity + maintenance + quality + community + architecture + dependency) / 6.0, 2)

    if archived:
        status = "archived"
    elif fork:
        status = "fork"
    elif commits_30d > 20 or prs_merged_90d > 5:
        status = "active"
    elif commits_30d > 0 or releases_90d > 0:
        status = "maintained"
    else:
        status = "dormant"

    name = str(r.get("full_name") or r.get("name") or "").lower()
    if re.search(r"(agent|mcp|aw|workflow|task|orchestrat)", name):
        layer = "agent/workflow"
    elif re.search(r"(quiz|game|idol|story|novel|music|anime)", name):
        layer = "content/product"
    elif re.search(r"(bqml|ml|model|ai|llm|yolo|qwen|lora|gan|vision)", name):
        layer = "ai/ml"
    elif re.search(r"(tui|ui|web|react|html|css|frontend)", name):
        layer = "interface"
    elif re.search(r"(ontology|schema|repo|wiki|data|db|sql)", name):
        layer = "data/knowledge"
    else:
        layer = "software"

    return {
        "full_name": r.get("full_name") or r.get("name"),
        "health_version": "1.0",
        "scoring_method": "deterministic-kaggle",
        "activity": activity,
        "maintenance": maintenance,
        "quality": quality,
        "community": community,
        "architecture": architecture,
        "dependency": dependency,
        "overall": overall,
        "status": status,
        "layer": layer,
        "fork": fork,
        "archived": archived,
        "language": r.get("language"),
        "stars": stars,
        "forks": forks,
        "size": size,
    }


def score_frame(df: pd.DataFrame) -> pd.DataFrame:
    rows = [score_row(rec) for rec in df.to_dict(orient="records")]
    return pd.DataFrame(rows)
