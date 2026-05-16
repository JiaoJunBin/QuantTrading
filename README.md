# QuantTrading

Personal quant research workspace built on the [QuantConnect LEAN CLI](https://www.quantconnect.com/docs/v2/lean-cli). Full project spec in [`docs/research_plan.md`](docs/research_plan.md).

## Layout

```
.
├── docs/research_plan.md  # Authoritative project spec — read first
├── research/              # QuantBook notebooks (run on QC cloud research)
├── strategies/            # One LEAN project per strategy combo
├── analysis/              # Shared factor tooling (pure pandas/scipy)
├── reports/               # Markdown reports + figures
├── scripts/               # QC REST API helpers
├── lean.json              # LEAN engine config
├── data/                  # Sample dataset (gitignored, ~226MB)
├── .env.example           # Copy to .env (gitignored) and fill in
└── CLAUDE.md              # Instructions for Claude Code in this repo
```

## Setup

```bash
# 1. Conda env + lean CLI (one-time)
conda create -n lean python=3.11 -y && conda activate lean
pip install lean scipy

# 2. Log in (writes ~/.lean/credentials)
lean login

# 3. Local credentials file for scripts/
cp .env.example .env
# Edit .env, or leave blank — scripts fall back to ~/.lean/credentials
```

## Running a backtest

Cloud is the default path (local backtest is blocked by infra — see CLAUDE.md):

```bash
lean cloud backtest "strategies/combo1_vwap_volume" --push
```

This pushes the project to QC, runs on the free B-MICRO node, and prints the statistics table. 0 QCC consumed for free datasets.

## Inspecting past results

The lean CLI has no command to show a previously-completed cloud backtest. Use the helpers in `scripts/`:

```bash
./scripts/bt_show.sh <backtest_id> -p <project_id>
```

Or open the report page directly: `https://www.quantconnect.com/project/<project-id>/<backtest-id>`

## Security

- `.env` and `~/.lean/credentials` hold the QC API token — treat as password-equivalent.
- Never paste the token in chat / commits / Slack. Rotate at https://www.quantconnect.com/account if leaked.
