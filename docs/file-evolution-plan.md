# ファイル進化計画（第 2 段）— 全 repo の GH メタデータ集計で何を知るか

**Status**: 計画（2026-11-12、TOY 上の opencode）
**親**: bonsai/wiki #396（進化計画）／ #395（予測照合実験）／ #386（特徴収集）／ #387（Kaggle Dataset）／ INTENT-02
**対象**: org 全 repo の GH メタデータ（**1,025 repo**、ローカル scan 340 repo）
**方針**: ML の出力は提案どまり。正は JSONL（Drive）、SQLite は処理エンジン、コードはこの repo。

この文書は #396 の計画を、**既存資産の整理**（§1）→ **マージ手順**（§2）→ **予測**（§3）→ **測定リスト**（§4）の順に具体化したもの。予測は `kaggle-prediction` skill のフェーズ 1 形式（反証可能な数値・状態付き）。測定後に §5 の表を埋めて照合する。

---

## 1. 既存（何があるか）— 順に整理

### 1.1 この repo（ml-repos-analyze）— ML コア
| 資産 | 状態 |
|---|---|
| `src/ml_repos_analyze/health.py` | 決定論 health スコア（BQML SQL 移植）。layer は repo 名判定・dependency 補正済み |
| `src/ml_repos_analyze/cluster.py` | sklearn KMeans（BQML の代役） |
| `src/ml_repos_analyze/bronze.py` | repositories.jsonl → repo_features 契約（欠損 0/False） |
| `src/ml_repos_analyze/enrich.py` | GraphQL バッチ収集（1 req ≈ 40 repo）+ recency プロキシ、`feature_source` 追跡 |
| `tools/collect_features.py` | commits_30d / ci / tests / lint / docs / manifest を収集（485/487 実績） |
| `tools/run_health_cluster.py` | bronze → health → cluster → レポート（--features / --proxy） |
| tests | 10 passed。コミット `01505db` `711fb2a`（push なし） |

### 1.2 repos-analyze（legacy・観測ハブ）— 進化の土台がここにある
| 資産 | 進化計画との関係 |
|---|---|
| `.github/workflows/repo-snapshot.yml` | **週次スナップショットの既存土台**。これを進化収集の入口にする |
| `snapshot/repo_snapshot.py` | gh repo list → CSV（full_name / stars / pushed_at 等） |
| `data/repositories.jsonl` | **1,025 repo の生メタデータ（collected_at 付き・単一時点）→ v1 スナップそのもの** |
| `data/repos.db` | repos 340 / issues 352（nested 339・dup-remote 13）/ repo_remotes 336 / **scans 3 バッチ** |
| `bqml/calculate_all_repo_health.sql` | health.py の元式（進化特徴の拡張もここに対応させる） |
| `analysis/statistics.py`, `bqml/trend_analysis.py` | 集計の先行例 |

### 1.3 .metadata / Drive（データの置き場）
- `exports/`: repos / projects / skills / unified の JSONL+CSV（manifest.json 付き）
- `reports/`: EDA 5 件、colab EDA、repos health cluster（素 / enriched）
- 進化データの置き場はここに追加: **`wiki/.metadata/evolution/`**（repo_snapshots / file_manifests / events）

### 1.4 wiki / 外部
- **#396**: 進化計画の 3 層（repo_snapshots / file_manifests / events）
- #395: 予測照合実験（skills 版はコーパス縮小 event で保留中）
- #387: Kaggle Dataset — parts 01/04/05 ready（**291 skills 検証済み**）。02/03 は消失原因未解決
- 事件の記録: custom-skills 484 → 35 dirs（2026-11-12 09:40 頃、痕跡なし）→ **進化追跡の必要性を実証した実例**。backup: `C:\Users\dance\skills-corpus-backup-20261112`

---

## 2. マージ計画（既存 → 進化レイヤを順に）

| Step | やること | 使う既存 | 完了条件 | 状態 |
|---|---|---|---|---|
| **0** | `repositories.jsonl`（1,025 行）→ `repo_snapshots.jsonl` v1（collected_at を captured_at に） | 1.2 の jsonl | Drive `evolution/` に 1 時点目が存在 | 次の一歩 |
| **1** | `tools/collect_manifests.py` — 全 repo の file manifest（path/size/blob_sha）を GraphQL trees で取得（~15 req） | enrich.py のバッチ方式 | 340 scan 対象の manifest 1 時点目 | 未 |
| **2** | `tools/diff_manifests.py` — 前回 vs 今回 → `events.jsonl`（added/removed/changed） | — | 2 時点目で events が出る | 未 |
| **3** | 週次化 — `repo-snapshot.yml` を拡張し Actions から収集、成果物は Drive へ | 1.2 の workflow | 手動実行なしで 2 週連続 capture | 未 |
| **4** | 分析統合 — `run_health_cluster.py --evolution` で churn/生存/成長を health 軸に追加 | health/cluster/enrich | 進化特徴つきレポート | 未 |
| **5** | skills 台帳の git 歴復元 — `skills/INDEX.yaml` の各コミット時点 → `skill_inventory.jsonl`（4 時点以上、12a90e1 = 463 skills） | git log（#396 で確認済み） | ≥4 時点の inventory 復元 | 未 |

原則: **スナップショットは追記のみ・不変**。差分と分析はいつでも再生成できる（派生）。

---

## 3. 予測 — 全 repo メタデータ集計から得られるインサイト

（`kaggle-prediction` フェーズ 1。確定済みの錨 → 予測 → 何を知るべきか。測定後に §5 で照合）

### 確定済みの錨（このセッションで実測）
- 1,025 repo = **own 487**（fork 278 / archived 260 を除く）
- 30 日以内に push した own repo: **~32（6.6%）**（GraphQL commits_30d → status maintained 30 + active 2）
- stars/forks はほぼ 0（community 軸平均 0.03/100）
- size 最大は YuE-extend 21 MB、次いで yuruteto 10.8 MB / yon-straydog 3.0 MB

### 予測（P1〜P12）

| # | 型 | 予測（反証可能） | 状態 |
|---|---|---|---|
| P1 | 誕生の時間構造 | created_at 月次ヒストグラムに 3 本以上のスパイクがあり、最大月が全体の >15% | 未検証 |
| P2 | 年齢 | repo 年齢（created_at から）の中央値は 180〜400 日 | 未検証 |
| P3 | 言語 | Python 35〜50% / JS・TS 20〜35% / language null 10〜25% | 未検証 |
| P4 | サイズ集中 | size 上位 10 repo が合計 size の >60% を占める | 未検証 |
| P5 | topics | topics 設定率 <20%（おそらく <10%） | 未検証 |
| P6 | 完全性 | license 記載 <30% / homepage 記載 <20% / description 記載 50〜80% | 未検証 |
| P7 | fork の鮮度 | fork の 90 日以内 push 率は own より高い（upstream 同期由来の偽の鮮度シグナル） | 未検証 |
| P8 | recency 曲線 | own の 90 日以内 push は 15〜25%（30 日 6.6% からの外挿） | 未検証 |
| P9 | big & dead | size 上位 20 のうち last_commit が 1 年以上前が過半 → 容量回収候補 | 未検証 |
| P10 | 名前空間 | repo 名のドメイン語（suno / crx / ml / kaggle / chira…）で 8〜12 個のクラスタ | 未検証 |
| P11 | file churn（manifest 導入後） | 最初の 2 時点の events は README・データ文件中心で、コード churn は repo の 2 割以下 | 未検証 |
| P12 | 消失検出 | manifest × 2 時点で「削除ファイル」が検出可能になる（custom-skills 事件の再発防止） | 未検証 |

---

## 4. 何を知るべきか（測定リスト — 定義つき）

| 指標 | 定義 | データ源 | 使途 |
|---|---|---|---|
| age | today − created_at（日） | repositories.jsonl | P1/P2、ライフサイクル分類 |
| recency | today − pushed_at（日）を 7/14/30/90/365 バケット | 同上 | P7/P8、dormant の質分類（done vs abandoned） |
| lang_mix | language の分布（null 含む） | 同上 | P3、言語 × 活動 |
| size_concentration | size 降順 top-N の累積シェア | 同上 | P4/P9、容量回収候補 |
| big_dead | size top20 ∧ last_commit ≥ 365 日 | 同上 + repos.db | P9、削除/アーカイブ提案 |
| field_completeness | description / homepage / license / topics の記載率 | 同上 | P5/P6、repo 衛生 |
| fork_freshness | fork の pushed_at 分布（own と比較） | 同上 | P7、fork 見直し |
| churn | manifest diff: added+removed+changed / total | file_manifests（Step 1 以降） | P11、進化特徴 |
| survival | ファイル/リポジトリが消えるまでの日数 | events | P12、消失検出 |
| growth | size・file 数の増減率 | manifests / snapshots | 成長 repo の特定 |
| commit_recency | commits_30d（GraphQL、既存） | enrich.py | activity 軸（実装済み） |

---

## 5. 予測 vs 実測（照合後に埋める）

| # | 予測 | 実測 | 判定 |
|---|---|---|---|
| P1 | スパイク ≥3、最大月 >15% | | |
| P2 | 中央値 180〜400 日 | | |
| P3 | Python 35〜50% / JS-TS 20〜35% / null 10〜25% | | |
| P4 | top10 で >60% | | |
| P5 | topics <20% | | |
| P6 | license <30% / homepage <20% / desc 50〜80% | | |
| P7 | fork の鮮度は偽 | | |
| P8 | 90 日以内 push 15〜25% | | |
| P9 | big&dead 過半 | | |
| P10 | クラスタ 8〜12 | | |
| P11 | コード churn ≤2 割 | | |
| P12 | 削除検出可能 | | |

---

## 6. 決定先（この分析が feeds する判断）

- **P4/P9** → 容量回収（houki / cleaner 系 workstream）への削除・アーカイブ候補リスト
- **P3 + recency** → どの言語生態系に投資するか（Muse 側の判断材料）
- **P5/P6** → repo 衛生の Story（topics・license の一括整備）
- **P7** → fork の見直し（upstream 追従 vs 削除）
- **P11/P12** → 進化追跡の運用評価（#396 の完了条件）

## 7. 運用上の約束

- 予測は必ず数値・幅つき（kaggle-prediction skill の規約）。外れたら理由を 3 分類（予測の偏り / 指標定義の不一致 / データの想定違い）で記す
- 収集は追記のみ。canonical は JSONL、SQLite は処理エンジン
- push はユーザー承認時のみ
