"""Feature enrichment for repo health (wiki #386).

Two sources, applied in order and always traceable per row:

1. **GitHub GraphQL collection** (`collect_features`) — real signals:
   commits on the default branch in the last 30 days, CI / tests / lint
   presence, docs entrypoint and manifest count. Batched through `gh api
   graphql` with aliases, so ~40 repos travel in one request.
2. **Recency proxy** (`apply_proxy`) — when API data is absent (no token,
   rate limit, private/missing repo), estimate `commits_30d` from
   `pushed_at`. A documented heuristic, never mixed silently: the row's
   `feature_source` says where its value came from ("api" / "proxy" /
   "none").
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone

import pandas as pd

API_FIELDS = ["commits_30d", "ci", "tests", "lint", "package_count"]

CI_FILES = {
    ".gitlab-ci.yml", "jenkinsfile", ".circleci", "azure-pipelines.yml",
    ".travis.yml", ".drone.yml", "bitbucket-pipelines.yml",
}
TEST_HINTS = {
    "test", "tests", "spec", "specs", "__tests__", "e2e",
    "pytest.ini", "tox.ini", "conftest.py", "jest.config.js",
    "vitest.config.ts", "karma.conf.js", "phpunit.xml",
}
LINT_FILES = {
    "ruff.toml", ".ruff.toml", ".flake8", ".eslintrc", ".eslintrc.js",
    ".eslintrc.json", ".eslintrc.yml", "eslint.config.js", "eslint.config.mjs",
    ".pre-commit-config.yaml", "biome.json", "pylintrc", ".pylintrc",
    ".rubocop.yml", ".golangci.yml", ".stylelintrc", ".shellcheckrc",
}
MANIFESTS = {
    "pyproject.toml", "setup.py", "package.json", "cargo.toml", "go.mod",
    "gemfile", "pom.xml", "build.gradle", "composer.json", "pubspec.yaml",
    "deno.json",
}

# (max age in days, estimated commits_30d) — first matching bucket wins.
PROXY_BUCKETS = ((7, 30), (14, 15), (30, 8), (90, 2))


# ---------------------------------------------------------------- GraphQL


def _batch_query(pairs: list[tuple[str, str]], since_iso: str) -> str:
    parts = []
    for i, (owner, name) in enumerate(pairs):
        parts.append(
            f'r{i}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) {{'
            f' defaultBranchRef {{ target {{ ... on Commit {{ history(since: "{since_iso}")'
            f" {{ totalCount }} }} }} }}"
            f' workflows: object(expression: "HEAD:.github/workflows")'
            f" {{ ... on Tree {{ entries {{ name }} }} }}"
            f' root: object(expression: "HEAD:")'
            f" {{ ... on Tree {{ entries {{ name type }} }} }}"
            f" }}"
        )
    return "query { rateLimit { cost remaining } " + " ".join(parts) + " }"


def _graphql(query: str, gh: str = "gh", timeout: float = 120.0) -> dict:
    payload = json.dumps({"query": query})
    proc = subprocess.run(
        [gh, "api", "graphql", "--input", "-"],
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    # gh exits non-zero when the response carries GraphQL errors (e.g. a
    # renamed repo), but the body still holds data for the aliases that
    # succeeded. Parse stdout first; fail only when there is no usable body.
    if proc.stdout.strip():
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            pass
    raise RuntimeError(f"gh api graphql failed: {proc.stderr.strip()[:400]}")


def root_signals(root_entries: list[dict], workflow_entries: list[dict]) -> dict:
    """Derive ci / tests / lint / documentation / package_count from a tree."""
    names = [str(e.get("name", "")).lower() for e in root_entries]
    blobs = {n for n in names}  # dirs included; presence is the signal
    ci = bool(workflow_entries) or any(n in blobs for n in CI_FILES)
    tests = any(
        n in TEST_HINTS or n.startswith("test_") or n.endswith("_test.py")
        or n.endswith(".test.js") or n.endswith("_test.go")
        for n in names
    )
    lint = any(n in LINT_FILES for n in names)
    documentation = any(n.startswith("readme") for n in names)
    package_count = sum(
        1 for n in names
        if n in MANIFESTS or n.startswith("requirements") and n.endswith(".txt")
    )
    return {
        "ci": ci,
        "tests": tests,
        "lint": lint,
        "documentation": documentation,
        "package_count": package_count,
    }


def collect_features(
    full_names: list[str],
    since: str | None = None,
    batch_size: int = 40,
    gh: str = "gh",
    timeout: float = 120.0,
    min_rate_remaining: int = 500,
    log=None,
) -> dict:
    """Collect activity features for many repos via batched GraphQL.

    Returns {full_name: {...features}} — repos that could not be read
    (renamed, private, deleted) map to None.
    """
    if since is None:
        since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    out: dict = {}
    names = list(full_names)
    for start in range(0, len(names), batch_size):
        chunk = names[start : start + batch_size]
        pairs = []
        for fn in chunk:
            owner, _, name = fn.partition("/")
            pairs.append((owner or "bonsai", name))
        body = _graphql(_batch_query(pairs, since), gh=gh, timeout=timeout)
        data = body.get("data") or {}
        rl = data.get("rateLimit") or {}
        if log:
            log(f"batch {start // batch_size + 1}: cost {rl.get('cost')} "
                f"remaining {rl.get('remaining')}")
        if rl.get("remaining", 10**9) < min_rate_remaining:
            if log:
                log("rate limit low, stopping early")
            for fn in chunk:
                out.setdefault(fn, None)
            break
        if body.get("errors"):
            # partial errors are fine; failed aliases come back as null
            if log:
                log(f"errors: {len(body['errors'])}")
        for i, fn in enumerate(chunk):
            node = data.get(f"r{i}")
            if not node:
                out[fn] = None
                continue
            history = ((node.get("defaultBranchRef") or {}).get("target") or {}).get(
                "history"
            ) or {}
            wf = ((node.get("workflows") or {}).get("entries") or [])
            root = ((node.get("root") or {}).get("entries") or [])
            signals = root_signals(root, wf)
            out[fn] = {
                "commits_30d": int(history.get("totalCount") or 0),
                **signals,
            }
    return out


# ------------------------------------------------------------------ merge


def apply_features(bronze: pd.DataFrame, feats: dict) -> pd.DataFrame:
    """Merge collected API features into the bronze frame, tracing source."""
    bronze = bronze.copy()
    source = []
    for idx, name in bronze["full_name"].items():
        f = feats.get(name)
        if f:
            bronze.at[idx, "commits_30d"] = float(f.get("commits_30d") or 0)
            for col in ("ci", "tests", "lint"):
                bronze.at[idx, col] = bool(f.get(col))
            bronze.at[idx, "package_count"] = float(f.get("package_count") or 0)
            source.append("api")
        else:
            source.append("none")
    bronze["feature_source"] = source
    return bronze


# ------------------------------------------------------------------ proxy


def proxy_commits(days_since_push: float) -> int:
    """Estimate commits_30d from push recency (documented heuristic)."""
    if days_since_push is None or pd.isna(days_since_push):
        return 0
    for limit, value in PROXY_BUCKETS:
        if days_since_push <= limit:
            return value
    return 0


def apply_proxy(
    bronze: pd.DataFrame,
    pushed_at: pd.Series,
    now: datetime | None = None,
) -> tuple[pd.DataFrame, int]:
    """Fill commits_30d from pushed_at where the API did not provide it."""
    bronze = bronze.copy()
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    pushed = pd.to_datetime(pushed_at, errors="coerce", utc=True)
    days = (now - pushed).dt.days
    applied = 0
    for idx, name in bronze["full_name"].items():
        if bronze.at[idx, "feature_source"] == "api":
            continue
        age = days.loc[idx] if idx in days.index else pd.NA
        value = proxy_commits(float(age)) if pd.notna(age) else 0
        bronze.at[idx, "commits_30d"] = float(value)
        if value > 0:
            bronze.at[idx, "feature_source"] = "proxy"
        applied += 1
    return bronze, applied
