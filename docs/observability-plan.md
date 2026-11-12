# LLM 観測基盤計画 — OpenRouter observability を参考に、Kaggle で自作する

**Status**: 計画（2026-11-12、TOY 上の opencode）。ユーザー指示「これらも使っていきたい。DB 分析プロバイダ。真似して Kaggle で自作すべきだが、参考にするまで」→ 本書は**参考研究と計画**のみ（実装は Step 0 から別途）。
**親**: bonsai/wiki #396（ファイル進化計画・姉妹）／ #384（OpenRouter キー）／ #395（kaggle-prediction 照合実験）
**対象データ**: LLM 呼び出し（provider / model / tokens / cost / latency / outcome）の観測。分析は Kaggle。

---

## 1. 参考 1 — OpenRouter observability（作りたいものの一覧）

`openrouter.ai/workspaces/<ws>/observability` が見せている機能:

| 機能 | 中身 |
|---|---|
| usage overview | 期間 × provider / model 別の requests・tokens・cost・errors |
| request logs | 1 リクエスト = 1 行（model, provider, status, tokens, cost, 時刻） |
| attempts | 1 リクエストの試行履歴（provider, key, outcome, retry, timing）— フォールバックの記録 |
| model catalog | context 長と価格（input / output per 1M tokens） |
| credits / balance | 残高と消化ペース |
| workspaces | プロジェクト単位の分離 |

## 2. 参考 2 — ngrok AI Gateway のデータモデル（実サンプリング済み）

opencode のツールカタログに AI Gateway 観測ツール群が入った（`aigw_*`）。**データモデルの参考**として実サンプリング:

- `aigw_usage_overview` — 期間集計（cost_usd / requests / errors / error_rate、by provider）。本アカウントは window 内 **0 usage**
- `aigw_list_models` — カタログ（context_length, input/output_usd_per_1m_tokens, surfaces）
- `aigw_get_request` / `aigw_get_request_attempts` — 1 リクエストの試行履歴（provider, key, outcome, retry, timing, tokens, cost）
- `aigw_get_capture` — body のキャプチャ
- **教訓**: 観測の単位は request → attempts（試行ごとに課金）→ provider/model で集計、の 3 段

## 3. 参考 3 — 既存 metrics.db（すでに半分ある）

`C:\Users\dance\.hamachi\metrics.db`（model-optimization skill の正。2026-11-12 実測）:

| テーブル | 行数 | 中身 |
|---|---|---|
| `model_metrics` | **518** | **リクエスト級**: run_id, model, provider, task, prompt, expected, response, smartness, response_time_ms, input_tokens, output_tokens, cost_usd, error, timestamp（3 run: run_20261018 / run_takt_20261111 / run_or_20261111） |
| `model_recommendations` | 72 | run 集計（avg_smartness / total_cost_usd / composite_score / rank） |
| `balance_snapshots` | 29 | OpenRouter 残高の時系列 |
| `usage_log` | **0** | スキーマのみ（model, tokens, cached_tokens, cost, timestamp）— **skill_evolution と同じ「設計先行・未計装」** |
| `forecast_log` | **0** | 残高予測（daily_avg, days_remaining）— 同じく未計装 |

注意: OpenRouter API 直接呼び出し（/api/v1/key, /credits）は **401**（User スコープ鍵 `sk-or-v1-0d6…` が拒否）。#384 の「恒久反映（opencode 再起動）」が未完の可能性 → 要確認。

---

## 4. 自作スキーマ（正は JSONL、Drive `wiki/.metadata/evolution/observability/`）

ファイル進化計画と同じ規約（1 行 = 1 エンティティ × 1 時点、追記のみ、SQLite は処理エンジン）:

- `llm_requests.jsonl` — 1 行 = 1 リクエスト: `{captured_at, surface, provider, model, key_label, outcome, attempts, input_tokens, output_tokens, cost_usd, latency_ms, source, run_id, error}`
- `balance_snapshots.jsonl` — 1 行 = 1 時点: `{captured_at, total_balance, granted, topped_up, currency}`
- `model_catalog.jsonl` — 1 行 = 1 モデル: `{model, provider, context_length, input_usd_per_1m, output_usd_per_1m, surfaces, captured_at}`

## 5. 収集源（3 系統）

1. **metrics.db エクスポート**（Step 0・新規収集ゼロ）: model_metrics 518 rows + balance_snapshots 29 rows → 上記 JSONL へ
2. **OpenRouter API 定期 pull**（鍵の恒久反映が前提）: credits / activity → provider 観測
3. **独自プロキシ**（将来）: 全 LLM 呼び出しを 1 箇所で記録する gateway（ngrok AI Gateway と同型）。takt / opencode / bench の全経路をこれに寄せる

## 6. Kaggle 分析（OpenRouter のページを模す）

| 分析 | 中身 | 相当 |
|---|---|---|
| usage overview | 期間 × provider / model の requests / tokens / cost / errors | observability トップ |
| per-model table | smartness × cost × latency（model_recommendations 拡張） | model leaderboard |
| error rate | モデル別・時間帯別（400 / 429 / 503） | request logs |
| **free 枠バーンダウン** | 日次 1000 req の消化ペース → 枯渇日予測 | forecast_log の実装 |
| balance 蒸発予測 | balance_snapshots の回帰 | credits ページ |

## 7. 予測（kaggle-prediction フェーズ 1 — 反証可能）

| # | 予測 | 状態 |
|---|---|---|
| Q1 | model_metrics 518 行のエラー率は 20〜40%（free モデルの 400/429 由来） | 未検証 |
| Q2 | 同一モデルの composite_score は run 間で ±0.1 以内に収まる（再現性） | 未検証 |
| Q3 | cost は free 枠中心で有料 usage は $0.50 枠の <10% | 未検証 |
| Q4 | 応答時間の中央値は free モデルで 2〜8 秒 | 未検証 |
| Q5 | usage_log は計装されるまで 0 行のまま | 未検証（負の予測） |

**何を知るべきか**: ①モデル別コスト効率（smartness / cost）②free 枠燃焼ペースと枯渇日 ③エラーの時間帯・モデル依存 ④run 間再現性（ベンチの信頼性）⑤usage_log 計装の効果

## 8. マージ Step

| Step | やること | 完了条件 | 状態 |
|---|---|---|---|
| **0** | `tools/export_observability.py` — model_metrics / balance_snapshots → JSONL | evolution/observability/ に llm_requests.jsonl（≥518 rows） | 未 |
| **1** | Kaggle notebook 01 — usage overview + per-model table | OpenRouter 風の 2 テーブルが再現 | 未 |
| **2** | OpenRouter API pull（鍵解決後）→ provider 観測 | credits が取得できる | 未（401） |
| **3** | usage_log 計装 — takt / opencode の呼び出しフック | usage_log > 0 rows | 未 |

## 9. 完了条件

- evolution/observability/ に llm_requests.jsonl（≥518 rows）と balance_snapshots.jsonl が存在
- Kaggle で usage overview（期間 × model の requests / tokens / cost / errors）が再現できる
- Q1〜Q5 の照合表が埋まる

## 10. 関連

- #396 ファイル進化計画（姉妹。進化＝リポジトリ軸、本計画＝LLM 利用軸）
- #384 OpenRouter キー（401 の恒久反映確認）/ #395 照合実験 / #387 Kaggle Dataset
- skill: model-optimization（metrics.db の正）/ free_quota_check（free 枠バーンダウンと統合）
- 参考: OpenRouter observability / ngrok AI Gateway（aigw_* ツール群）
