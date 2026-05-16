# Claude instructions for QuantTrading

## Project shape
QuantConnect LEAN CLI project. Root holds `lean.json` (engine config) and `data/` (sample dataset, gitignored, ~226MB). Each strategy is a subdir with `main.py` + `config.json` + optional `research.ipynb`.

## Backtests run in the cloud, not locally
Default to `lean cloud backtest "<project>" --push`. **Do not suggest `lean backtest` (local).** The vscode-server pod's DinD sidecar (in `cmb/ali-kube-deployments/bases/vs-code-server/deployment.yaml`) has `limits.memory: 2Gi` and `emptyDir` for `/var/lib/docker` — pulling the ~2-3GB LEAN image OOM-kills DinD and the pod gets recreated, wiping the image cache. Until both are fixed (raise DinD limit to 6-8Gi AND switch docker-graph-storage to a PVC, via the ali-kube-deployments repo + ArgoCD), local backtests will keep failing.

Cloud backtests use the free B-MICRO node and burn 0 QCC unless the strategy downloads premium datasets or runs `lean cloud optimize`.

## Credentials
`lean login` stores user-id + api-token in `~/.lean/credentials`. `scripts/_common.sh` reads from `.env` first, falls back to that file. **Never paste the API token in chat** — rotate at https://www.quantconnect.com/account if it leaks. `.env` is gitignored.

## scripts/
Bash helpers for the QC REST API. The lean CLI has no command to show a past cloud backtest's results, so we hit the API directly.

- `scripts/_common.sh` — sourced; exposes `qc_api <endpoint> <json-body>` with HMAC signing
- `scripts/bt_show.sh <backtest_id>` — prints statistics table for one backtest

Add new helpers (list backtests, fetch orders, etc.) by sourcing `_common.sh` and calling `qc_api`.

## External data access in algorithms
Cloud algorithms cannot use `requests` / `urllib` — QC blocks them. Use `self.download(url)` (rate-limited, ~100 calls/backtest, fails silently) or define a `PythonData` subclass with `GetSource()` + `Reader()`. Local LEAN has no such restriction. See `Sample Strategy/main.py` for the algorithm shape.

## Style
- Don't add files unless asked. No README rewrites, no docs scaffolding.
- Keep commits small and focused; messages describe the *why*.
- For anything touching ali-kube-deployments or the vscode pod config, confirm with the user first — that's shared infra.
