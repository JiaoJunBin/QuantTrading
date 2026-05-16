# Strategy Backtest Report

**Strategy**: U11 + residual_mom + n=4 + rank weighting
**Document version**: 2.0 (QC cloud anchored)
**Generated**: 2026-05-16
**Primary backtest window**: 2010-01-04 to 2026-05-15 (16.4 years on QC cloud)

---

## 1. Strategy specification

### Universe (11 ETFs)

| Asset class | Tickers |
|---|---|
| US equity | SPY, QQQ |
| International | EFA, VWO |
| Rates | TLT (long bonds), IEF (medium bonds) |
| Credit | HYG (high yield) |
| Commodities | GLD, DBC |
| Sector | SOXX (semiconductors) |
| Real assets | VNQ (REITs) |

**Excluded by design**: IWM (small caps — see diagnostic D below), single stocks, sector ETFs other than SOXX.

### Signal

**Residual momentum** (alpha momentum / idiosyncratic momentum):

For each asset at time `t`:

```
sym_rets = pct_change over t-252 to t-21
spy_rets = same window of SPY pct_change
beta     = cov(sym_rets, spy_rets) / var(spy_rets)
signal   = sum(sym_rets[i] - beta * spy_rets[i]) for i in window
```

Strips market beta, leaving each asset's idiosyncratic component of 12-1 momentum.

### Position sizing — rank weighting

Each month, rank assets by signal. Take top `n=4` with positive momentum.

| Rank | Weight |
|---|---|
| 1 | 40% |
| 2 | 30% |
| 3 | 20% |
| 4 | 10% |

Fewer than 4 positives → cash fills the unused slots. All negative → 100% cash.

### Rebalance cadence

Monthly. First trading day at 10:00 ET. Manual execution via `manual/monthly_rebalance.ipynb`.

### Costs modeled in QC backtest

- Commission: IBKR Pro Tiered ($0.0035/share, min $0.35) + $0.10 venue fee + 9% Singapore GST
- Slippage: 5 basis points each way (`ConstantSlippageModel(0.0005)`)
- Margin account, no leverage actually used

---

## 2. QC Cloud Backtest URLs

All hosted under project `3d_xsmom_v2` (id `31740853`). [Project link](https://www.quantconnect.com/project/31740853)

| Test | Backtest URL |
|---|---|
| **Baseline full 2010-2026** | [link](https://www.quantconnect.com/project/31740853/ac3af54fd9cb2dc92f0ae263586e23f6) |
| IS (2010-2018, 9 years) | [link](https://www.quantconnect.com/project/31740853/d40fe40e66e6813dce256eaa7e4ff2e0) |
| OOS (2019-2026, 7.4 years) | [link](https://www.quantconnect.com/project/31740853/c1e094dc463975558fad6a720fda34e2) |
| No SOXX (U10) | [link](https://www.quantconnect.com/project/31740853/7415889557dcbe78f1f3ffbaf26bb5dd) |
| n=2 (concentrated) | [link](https://www.quantconnect.com/project/31740853/a6fb0b67dc57ef97d4ddb2d0d136bcc9) |
| n=3 (middle) | [link](https://www.quantconnect.com/project/31740853/b57ec429240e79652f3cf012ece58a13) |
| Equal weighting (vs rank) | [link](https://www.quantconnect.com/project/31740853/574328a16aeb97b77d93b0eee1667451) |

---

## 3. Headline results — QC cloud baseline

**Window**: 2010-01-04 to 2026-05-15 (16.4 years, $100k initial)
**Config**: U11 + residual_mom + n=4 + rank weighting

| Metric | Strategy | SPY B&H (same window) |
|---|---|---|
| CAGR | **13.63%** | 14.26% |
| Sharpe | **0.778** | 0.864 |
| Max drawdown | **-17.6%** | -33.7% |
| Total return | +710% | +782% |
| Final equity | $810k | $878k |
| PSR | 38.7% | — |
| Win rate | 75% | — |
| Annual std | 9.8% | 16.7% |
| Total orders | 800 | 1 |
| Total fees | $1,275 (16 yr) | $1 |

**Verdict**:
- Strategy **slightly underperforms** SPY on CAGR (-0.6pp) and Sharpe (-0.09) over the full 16 years
- Strategy **dramatically lower drawdown** (-17.6% vs -33.7%) — half of SPY's worst loss
- Strategy uses lower volatility (9.8% vs 16.7%) → smoother path
- **Not a CAGR-beater on this window**, but provides clear risk advantage

⚠️ **IMPORTANT**: This is **lower performance than local yfinance prototype** (which had Sharpe 1.20). Discrepancy explained in Section 7.

---

## 4. IS / OOS split (QC cloud)

To check for overfitting / regime dependence:

| Period | Years | CAGR | Sharpe | MDD | PSR |
|---|---|---|---|---|---|
| **IS** (2010-2018) | 9 | 7.67% | **0.52** | -17.9% | **9.3%** |
| **OOS** (2019-2026) | 7.4 | **21.00%** | **1.03** | -13.5% | **76.7%** |
| Full (2010-2026) | 16.4 | 13.63% | 0.78 | -17.6% | 38.7% |

**Two critical observations**:

1. **OOS > IS** by a factor of 2x on Sharpe. This is the **opposite of classic overfitting** (which shows IS >> OOS).

2. **PSR explosion in OOS**: IS PSR 9.3% means strategy had near-zero statistical evidence of real alpha in 2010-2018. OOS PSR 76.7% means strong evidence in 2019-2026.

**Interpretation**: 2010-2018 was a long single-direction bull market where cross-asset rotation added minimal value. 2019-2026 included COVID crash (2020), 2022 bear, 2023-25 rotation — **regime-shift environments are when this strategy earns its keep**.

**Risk**: if next 5-10 years resembles 2010-2018 (long bull, low vol), strategy will underperform SPY in absolute terms. Forward Sharpe in such a regime is ~0.5.

---

## 5. SOXX sensitivity (QC cloud)

SOXX (semiconductors) is in top 4 about 26% of months. **Concern**: 2017-2024 semi super-cycle inflated results.

| Universe | CAGR | Sharpe | MDD | PSR |
|---|---|---|---|---|
| U11 (with SOXX) | 13.63% | **0.778** | -17.6% | 38.7% |
| **U10 (no SOXX)** | 9.45% | **0.539** | -17.9% | 11.2% |
| **Δ from dropping SOXX** | **-4.18pp** | **-0.239** | -0.3pp | -27.5pp |

**SOXX contributes ~0.24 Sharpe** (31% of full Sharpe). Local yfinance estimate was 0.27 — both methods consistent.

**Without SOXX, strategy underperforms SPY** (Sharpe 0.54 vs 0.86). U10 is essentially "diversified bond/gold rotation with some equity exposure" — defensive but not market-beating.

**Risk**: if semi super-cycle ends (e.g., 2026+ semi cycle peaks, AI capex slows), strategy loses meaningful alpha. **Watch SOXX pick frequency: > 40% of months is a red flag**.

---

## 6. Position concentration (long_n) sweep — QC cloud

| Config | CAGR | Sharpe | MDD | PSR | Final $100k |
|---|---|---|---|---|---|
| n=2 (max concentration) | **16.19%** | 0.765 | **-24.9%** | 27.4% | $1.17M |
| n=3 | 14.89% | **0.788** | -21.9% | 36.2% | $971k |
| **n=4** (baseline) | 13.63% | 0.778 | **-17.6%** | **38.7%** | $810k |

**Trade-off**:
- n=2: highest CAGR (+2.6pp vs n=4) but much bigger MDD (+7.3pp)
- n=3: best Sharpe by a hair (+0.01 vs n=4), modest MDD increase
- **n=4: lowest MDD, highest PSR, simplest to execute**

**Decision rationale for n=4**:
- MDD 17.6% is psychologically manageable on $20k init account
- PSR 38.7% is highest — statistically most defensible
- Lower turnover → less tax drag (relevant for taxable accounts)

For users who can tolerate -25% drawdown and want higher CAGR, n=2 or n=3 are valid alternatives.

---

## 7. Weighting scheme — QC cloud

| Scheme | CAGR | Sharpe | MDD | Notes |
|---|---|---|---|---|
| **Rank** (40/30/20/10) | 13.63% | **0.778** | -17.6% | Top pick gets 4x bottom pick weight |
| Equal (25 each) | 11.76% | 0.687 | **-16.3%** | All 4 picks same weight |

**Rank wins**:
- +1.87pp CAGR
- +0.09 Sharpe
- Cost: +1.3pp MDD (acceptable)

Local yfinance previously found rank > equal by ~0.06 Sharpe. QC confirms with slightly larger margin (+0.09).

---

## 8. Local yfinance vs QC cloud — why numbers differ

The local prototyping (yfinance + custom Python simulator) consistently showed higher Sharpe and lower MDD than QC cloud:

| Metric | Local yfinance | QC cloud | Δ |
|---|---|---|---|
| CAGR | 14.30% | 13.63% | -0.67pp |
| Sharpe | 1.20 | 0.78 | **-0.42** |
| MDD | -15.6% | -17.6% | -2.0pp |

**Sources of discrepancy**:

1. **Commission + GST not modeled locally** — QC charged $1,275 over 16 years on $100k. Small absolute but compounds.
2. **Slippage not modeled locally** — QC applied 5bp roundtrip = ~10bp per trade. With 800 trades over 16 years, that's a measurable drag.
3. **Data adjustments** — yfinance uses Yahoo's auto-adjusted prices; QC uses Quandl/IEX feeds with slightly different split/dividend handling.
4. **Sharpe formula nuances** — QC's Sharpe includes annualization conventions that may differ slightly from a naive `mean/std × sqrt(252)`.

**Implication**: **trust QC numbers for forward expectations**. The local yfinance Sharpe 1.20 was prototype-grade — useful for direction-finding among 100+ configurations, but not the realistic backtest.

---

## 9. Forward expectations (recalibrated)

Anchored on QC numbers, not local yfinance:

| Metric | QC baseline | **Realistic forward** | Justification |
|---|---|---|---|
| Sharpe | 0.78 | **0.5 - 0.7** | Past 16yr Sharpe degrades in implementation by 20-40% (commission/slippage estimates, regime shift) |
| CAGR | 13.6% | **9 - 12%** | Similar regime expected over next 5-10 years; haircut for SOXX cycle risk |
| Max drawdown | -17.6% | **-20% to -28%** | New regime might have larger drawdowns; CSC stress (e.g., 2008-style) untested |
| Win rate (monthly) | 75% | **55 - 65%** |  Above-average win rate appears to depend on momentum regime |

**Critical edge cases that historical backtest didn't fully exercise**:
- 2008-style cross-asset crash (all major asset classes down 30%+ simultaneously). Our 16yr starts after Q1 2010.
- Multi-year stagflation (1970s) — only have 2 quarters of mild 2022 inflation in sample
- Sustained low-vol bull market 5+ years (2013-2016, 2017 were these — strategy did poorly in IS)

---

## 10. Diagnostic D — IWM exclusion rationale

We tested adding/removing IWM (small-cap ETF) on QC cloud earlier (in 3d_xsmom_lo project), finding:

| Universe | Sharpe | MDD |
|---|---|---|
| With IWM (6-ETF original) | 0.90 | -25.5% |
| Without IWM (5-ETF) | **1.00** | **-22.9%** |

IWM was picked in 14-16% of months and consistently underperformed. **Small caps don't share large-cap momentum dynamics** (Fama-French 2012 finding: small-cap momentum has weaker IC than large-cap). U11 deliberately excludes IWM.

---

## 11. DCA comparison ($20k initial + $3k/month) — local sim

For someone investing $20k initially + $3k/month over 11.4 years (total $429k deposited):

| Scenario | Final equity | ROI on deposited | Max drawdown |
|---|---|---|---|
| **Strategy DCA** | ~$2.54M | +317% | **-15%** |
| SPY DCA | $2.43M | +300% | -33% |
| QQQ DCA | $4.10M | +575% | -34% |

Strategy DCA beats SPY DCA by ~$110k with half the drawdown. Loses to QQQ DCA by $1.5M+ but with much better drawdown control.

⚠️ This DCA analysis was run locally (yfinance) before discovering QC's lower Sharpe. **Real forward DCA outcome likely ~70-85% of these numbers** due to costs.

---

## 12. Pick frequency over 16 years (full QC backtest)

From the QC backtest's 800 orders (~200 monthly rebalances):

| Ticker | ~Pick freq | Role |
|---|---|---|
| GLD | 45% | Safe haven anchor |
| TLT | 40% | Long-duration play |
| **SOXX** | **26%** | Equity beta (critical contributor) |
| DBC | 23% | Commodities |
| QQQ | 20% | Tech beta |
| VNQ | 17% | Real assets |
| IEF | 12% | Mid-duration |
| EFA | 4% | International |
| HYG | 4% | Credit |
| VWO | 3% | Emerging |
| SPY | 1% | Rarely top-4 vs other asset classes |

**Insight**: bonds + gold dominate the long-term picks. SOXX captures equity uplift selectively. SPY almost never selected — its broad-market beta gets dominated by more concentrated alternatives.

**Strategy is genuinely rotating**: 25 unique top-2 pairs over 16 years, longest same-pair streak only 11 months.

---

## 13. Known limitations and caveats

1. **Multiple testing bias**: Final configuration emerged after exploring 100+ variants. Even with the IS/OOS split, some leakage of post-2018 knowledge into universe/parameter choices is inevitable.

2. **SOXX dependency**: 31% of Sharpe from SOXX. Single-sector concentration risk if semi cycle reverses.

3. **Slippage assumption**: 5bp may understate real slippage in less liquid ETFs (VWO, HYG). Real fills could be 5-10bp worse than backtest.

4. **Tax inefficient**: Monthly rebalance creates frequent short-term gains. In US taxable accounts, post-tax returns will be materially lower (potentially -3pp/yr).

5. **Regime sensitivity**: Strategy works best in regime-shift markets. In sustained low-vol bull (like 2010-2018 IS), Sharpe drops to ~0.5.

6. **Data quality**: yfinance prototype used Yahoo data; QC uses Quandl/IEX. Some divergence in adjusted prices is normal.

7. **Survivorship bias**: All 11 universe assets are still trading in 2026. If we had picked an ETF that delisted, hindsight bias is absent — but we deliberately chose well-known liquid names.

---

## 14. Manual execution

See `manual/monthly_rebalance.ipynb`. Workflow:
1. First trading day of each month, fill in current IBKR holdings + cash
2. Run all cells (uses yfinance for live signal computation)
3. Output is a trade list ready for IBKR market orders
4. Decision log auto-saved to `rebalance_log_YYYY-MM-DD.txt`

Approximate execution time: 3-5 minutes/month.

---

## 15. Decision points for ongoing operation

**When to NOT trust the strategy**:
- Implementing in a brand new regime (e.g., 2025+ might have very different momentum dynamics from 2015-2024)
- If SOXX appears in top-4 > 50% of months for 12+ consecutive months — strategy has degenerated to single-sector bet
- If forward Sharpe stays below 0.4 for 6+ months — pause and reassess

**When to consider scaling up**:
- 6+ months of paper trading with realized Sharpe close to backtest expectation (0.5+)
- No single asset > 50% of long-run P&L attribution
- MDD experienced live stays within forward expectation (-28% threshold)

**Periodic review**:
- Quarterly: check pick frequency vs. backtest distribution (Section 12)
- Annually: full re-run of QC backtest with another year of data appended
- Never re-tune universe or parameters based on recent results — that's overfitting

---

## 16. Summary one-liner

> **Risk-controlled equity overlay**: U11 cross-asset momentum rotation with rank weighting that delivers roughly SPY-comparable Sharpe (0.78) at half the drawdown (-17.6% vs -33.7%) over 2010-2026 on QC cloud. Strategy concentrates value-add in regime-shift periods (OOS 2019-2026 Sharpe 1.03) and struggles in long single-direction bull markets (IS 2010-2018 Sharpe 0.52). About 31% of Sharpe comes from SOXX participation — a known concentration risk. Realistic forward Sharpe 0.5-0.7, CAGR 9-12%, MDD -20% to -28%. Executed manually each month via the `manual/monthly_rebalance.ipynb` notebook.

---

## 17. Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-16 | Strategy v1 = U11 + residual_mom + n=4 + rank | Best risk-adjusted config in QC backtest sweep. n=4 preferred over n=3 for MDD; rank > equal weighting by 0.09 Sharpe |
| 2026-05-16 | Drop IWM, drop XOM, drop USO, no BTC sleeve | Per Diagnostic D (IWM hurts), and per user's preference to handle BTC manually outside the strategy |

---

## 18. Related artifacts

- **Trading notebook**: `manual/monthly_rebalance.ipynb`
- **QC strategy code**: `strategies/3d_xsmom_v2/` (cloud-id `31740853`)
- **Project spec**: `docs/research_plan.md`
- **Diagnostic scripts** (local prototyping, in `/tmp/` during research, not committed):
  - `robustness_tests.py` — IC, sub-period, regime, cross-asset
  - `deep_dive.py` — range market, SOXX, IWM, QQQ IC stability
  - `universe_concentration_sweep.py` — 3 universes × 4 n × 2 signals
  - `weighting_sweep.py` — 4 weight schemes × 4 n × 2 universes × 3 periods
  - `btc_sleeve_xom.py` — BTC sleeve sizing + XOM/USO/XLE comparison
  - `diagnostics.py` — SOXX sensitivity, concentration, clean OOS validation
