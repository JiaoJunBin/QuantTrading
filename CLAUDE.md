# Claude instructions for QuantTrading

## Project purpose
Build and validate 3-4 volume/price-indicator strategy combos (mean-reversion, trend, climax) on US equities (SPY/QQQ/IWM, 15-min bars). Full spec in `docs/research_plan.md` — read it before any non-trivial change. The deliverable is **an honest comparison report**, not a guaranteed-profitable strategy; negative results are valid outputs.

## Layout
```
docs/research_plan.md     # Authoritative project spec
research/                 # QuantBook notebooks (run on QC cloud research)
strategies/comboN_*/      # Each is a LEAN project (main.py + config.json)
analysis/                 # Pure-python factor tooling (no LEAN deps)
scripts/                  # QC REST API helpers (bt_show.sh etc.)
data/                     # Sample dataset, gitignored (~226MB, regenerable)
lean.json                 # Engine config
```

## Backtests run in the cloud, not locally
Default to `lean cloud backtest "<project>" --push`. **Do not suggest `lean backtest` (local).** The vscode-server pod's DinD sidecar (in `cmb/ali-kube-deployments/bases/vs-code-server/deployment.yaml`) has `limits.memory: 2Gi` and `emptyDir` for `/var/lib/docker` — pulling the ~2-3GB LEAN image OOM-kills DinD and the pod gets recreated, wiping the image cache. Same applies to `lean research` (local Jupyter). Until DinD is bumped to 6-8Gi AND `docker-graph-storage` switches to a PVC (via ali-kube-deployments + ArgoCD), everything Docker-backed stays on QC cloud.

Cloud backtests use the free B-MICRO node and burn 0 QCC unless the strategy downloads premium datasets or runs `lean cloud optimize`.

## Research workflow (from research_plan.md §3)
For every indicator / strategy, in this order — **do not skip steps**:

1. **IC analysis** (`analysis/ic_calculator.compute_ic`). Reject if `|IC| < 0.02`.
2. **Quantile test** — bucket-monotonicity check. Flat or U-shaped → reject.
3. **Robustness**: parameter sensitivity ±20%, walk-forward IS/OOS, bull/bear/range regime split.
4. **Backtest** with realistic costs: `IBKRSingaporeFeeModel` (IBKR Pro Tiered + 9% GST), `ConstantSlippageModel(0.0005)`, margin ≤ 1.5×.
5. **Report** with IS/OOS clearly separated, no cherry-picked parameters.

The four target combos: `combo1_vwap_volume`, `combo2_obv_breakout`, `combo3_mfi_meanrev`, `combo4_volume_climax`. Specs in `docs/research_plan.md §2`.

## IS/OOS discipline (non-negotiable)
- **In-sample is at most 60% of the data**. Default split: 2018–2021 IS, 2022–2024 OOS.
- Any parameter touched on IS data is "burned" for OOS — never reuse for the same purpose.
- Report IS and OOS numbers side by side. If only one is shown, the result is invalid.
- If OOS Sharpe < 60% of IS Sharpe, declare the strategy overfit and move on.

## Common-pitfall checklist
Before reporting any backtest result, confirm:
- No look-ahead (used `shift(-n)` not `shift(n)` for forward returns; signals use `bar.close` of bar t, trade at bar t+1).
- No survivorship bias (started with the universe as it existed at backtest start, not today's universe).
- Transaction costs and slippage modeled, not zero.
- Warm-up period (`set_warm_up`) covers the longest indicator lookback.

## Credentials and secrets
`lean login` writes `~/.lean/credentials`. `scripts/_common.sh` loads `.env` (gitignored) and falls back to that file. **Never paste the API token in chat** — rotate at https://www.quantconnect.com/account if it leaks.

## scripts/
Bash helpers for the QC REST API; the lean CLI has no command to show a past cloud backtest's results, so we hit the API directly.

- `scripts/_common.sh` — sourced; exposes `qc_api <endpoint> <json-body>` with HMAC signing
- `scripts/bt_show.sh <backtest_id> [-p <project_id>]` — print statistics table for one backtest

Add new helpers (list backtests, fetch orders, fetch equity curve) by sourcing `_common.sh` and calling `qc_api`.

## Shared code across QC cloud projects (Option A: manual copy)
`lean cloud push --project X` only uploads files inside `X/`. Sibling dirs like `analysis/` are invisible to cloud. Convention for this repo:

- **`analysis/ic_calculator.py` is the single source of truth.** Edit it here, run unit-tests / smoke-tests against it locally.
- **When a notebook or strategy needs IC tooling on QC cloud, copy `analysis/ic_calculator.py` into that project directory** before `lean cloud push`. The copy lives alongside `main.py` / the .ipynb. Import as `from ic_calculator import ...` (no `analysis.` prefix because it's flat in the project root).
- After editing the canonical file in `analysis/`, re-copy into every project that has a stale copy. There's no auto-sync — keep the consumer list short.
- For research notebooks that run **purely locally** (Jupyter on the host, no Docker, no QuantBook), no copy is needed — `sys.path.insert(0, '..')` lets the notebook import directly from `analysis/`. See `research/01_data_exploration.ipynb` cells for the pattern.

## Local execution does NOT require Docker
Only LEAN-engine commands (`lean backtest`, `lean research`) need Docker. Plain `python script.py` or `jupyter lab` against this repo runs with zero Docker dependency. The DinD issue only matters for the LEAN engine path; pure-Python factor analysis using `analysis/ic_calculator.py` + cached data is unaffected. `QuantBook` (QC's data API) only works inside the LEAN runtime — so notebooks that use `QuantBook` must run on QC cloud (web UI or `lean research`), while notebooks using a non-QC data source (yfinance, locally cached parquet) can run as plain Jupyter.

## External data access in algorithms
Cloud algorithms cannot use `requests` / `urllib` — QC blocks them. Use `self.download(url)` (rate-limited, ~100 calls/backtest, fails silently) or define a `PythonData` subclass with `GetSource()` + `Reader()`. Local LEAN has no such restriction but local execution is blocked — see above.

## Style
- Don't add files unless asked. The deliverable list is in `docs/research_plan.md §5` — stick to it.
- One commit per phase; commit message records the headline metric (e.g. `Phase 2: VWAP IC=0.052 (1d), OBV IC=0.038`).
- Report negative results truthfully. "This indicator failed" is a valid deliverable.
- Anything touching `cmb/ali-kube-deployments` is shared infra — confirm with user first.
