# QuantTrading

Personal quant research workspace built on the [QuantConnect LEAN CLI](https://www.quantconnect.com/docs/v2/lean-cli).

## Layout

```
.
├── lean.json              # LEAN engine config
├── data/                  # Sample dataset (gitignored; regenerate via `lean init`)
├── Sample Strategy/       # Each strategy is a subdir
│   ├── main.py
│   ├── config.json        # cloud-id links to QC project
│   └── research.ipynb
├── scripts/               # QC REST API helpers (see below)
├── .env.example           # Copy to .env and fill in
└── CLAUDE.md              # Instructions for Claude Code in this repo
```

## Setup

```bash
# 1. Conda env + lean CLI (one-time)
conda create -n lean python=3.11 -y && conda activate lean
pip install lean

# 2. Log in (writes ~/.lean/credentials)
lean login

# 3. Local credentials file for scripts/
cp .env.example .env
# Edit .env, or leave blank — scripts fall back to ~/.lean/credentials
```

## Running a backtest

Cloud is the default path (local backtest is blocked by infra constraints — see CLAUDE.md):

```bash
lean cloud backtest "Sample Strategy" --push
```

This pushes local code to QC, runs on the free B-MICRO node, and prints the statistics table. 0 QCC consumed for free datasets.

## Inspecting past results

The lean CLI has no command to show a previously-completed cloud backtest. Use the helpers in `scripts/`:

```bash
./scripts/bt_show.sh <backtest_id>
# e.g.
./scripts/bt_show.sh a3423b5b356ad811fca08df42e9b4e28
```

Or open the report page in a browser:
`https://www.quantconnect.com/project/<project-id>/<backtest-id>`

## Security

- `.env` and `~/.lean/credentials` hold the QC API token — treat as password-equivalent.
- Never paste the token in chat / commits / Slack. Rotate at https://www.quantconnect.com/account if leaked.
