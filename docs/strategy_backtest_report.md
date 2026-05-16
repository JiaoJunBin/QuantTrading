# 策略 Backtest 报告

**策略**：U11 + residual_mom + n=4 + rank weighting
**文档版本**：2.0（QC cloud 锚定）
**生成日期**：2026-05-16
**主要 backtest 窗口**：2010-01-04 至 2026-05-15（QC cloud 上 16.4 年）

---

## 1. 策略规范

### Universe（11 个 ETF）

| 资产类别 | Tickers |
|---|---|
| 美股 | SPY, QQQ |
| 国际市场 | EFA, VWO |
| 利率 | TLT（长债）, IEF（中期债） |
| 信用 | HYG（高收益债） |
| 商品 | GLD, DBC |
| 行业 | SOXX（半导体） |
| 实物资产 | VNQ（REITs） |

**故意排除的**：IWM（小盘股——见下面 Diagnostic D）、单股、SOXX 以外的行业 ETF。

### Signal

**Residual momentum**（alpha momentum / idiosyncratic momentum）：

对每个资产在时间 `t`：

```
sym_rets = t-252 到 t-21 的 pct_change
spy_rets = 同窗口的 SPY pct_change
beta     = cov(sym_rets, spy_rets) / var(spy_rets)
signal   = sum(sym_rets[i] - beta * spy_rets[i]) over window
```

剥除市场 beta，剩下每个资产对 12-1 momentum 的特异部分。

### 仓位分配——rank weighting

每月按 signal 排序资产。取正动量的前 `n=4`。

| Rank | Weight |
|---|---|
| 1 | 40% |
| 2 | 30% |
| 3 | 20% |
| 4 | 10% |

正动量不足 4 个 → 现金填空位。全负 → 100% 现金。

### 调仓节奏

月度。第一个交易日 10:00 ET。手动执行通过 `manual/monthly_rebalance.ipynb`。

### QC backtest 中建模的成本

- 佣金：IBKR Pro Tiered ($0.0035/股，最低 $0.35) + $0.10 venue fee + 9% Singapore GST
- 滑点：单边 5 个基点（`ConstantSlippageModel(0.0005)`）
- Margin 账户，实际未使用 leverage

---

## 2. QC Cloud Backtest URLs

全部在 project `3d_xsmom_v2`（id `31740853`）下。[Project 链接](https://www.quantconnect.com/project/31740853)

| 测试 | Backtest URL |
|---|---|
| **Baseline 全 2010-2026** | [link](https://www.quantconnect.com/project/31740853/ac3af54fd9cb2dc92f0ae263586e23f6) |
| IS (2010-2018，9 年) | [link](https://www.quantconnect.com/project/31740853/d40fe40e66e6813dce256eaa7e4ff2e0) |
| OOS (2019-2026，7.4 年) | [link](https://www.quantconnect.com/project/31740853/c1e094dc463975558fad6a720fda34e2) |
| No SOXX（U10） | [link](https://www.quantconnect.com/project/31740853/7415889557dcbe78f1f3ffbaf26bb5dd) |
| n=2（更集中） | [link](https://www.quantconnect.com/project/31740853/a6fb0b67dc57ef97d4ddb2d0d136bcc9) |
| n=3（中间） | [link](https://www.quantconnect.com/project/31740853/b57ec429240e79652f3cf012ece58a13) |
| Equal weighting（vs rank） | [link](https://www.quantconnect.com/project/31740853/574328a16aeb97b77d93b0eee1667451) |

---

## 3. 头部结果——QC cloud baseline

**窗口**：2010-01-04 至 2026-05-15（16.4 年，$100k 起始）
**配置**：U11 + residual_mom + n=4 + rank weighting

| 指标 | 策略 | SPY B&H（同窗口） |
|---|---|---|
| CAGR | **13.63%** | 14.26% |
| Sharpe | **0.778** | 0.864 |
| Max drawdown | **-17.6%** | -33.7% |
| 总回报 | +710% | +782% |
| 最终资金 | $810k | $878k |
| PSR | 38.7% | — |
| Win rate | 75% | — |
| Annual std | 9.8% | 16.7% |
| 总订单数 | 800 | 1 |
| 总 fees | $1,275（16 年） | $1 |

**判定**：
- 全 16 年策略在 CAGR 上**略输** SPY（-0.6 pp）、Sharpe（-0.09）
- 策略**回撤显著低**（-17.6% vs -33.7%）——SPY 最差损失的一半
- 策略用更低的波动率（9.8% vs 16.7%）→ 平滑路径
- 这个窗口上**不是 CAGR 击败者**，但提供清晰的风险优势

⚠️ **重要**：这比本地 yfinance prototype 低（那个 Sharpe 1.20）。差异在 Section 7 解释。

---

## 4. IS / OOS 切分（QC cloud）

检查过拟合 / regime 依赖：

| Period | 年数 | CAGR | Sharpe | MDD | PSR |
|---|---|---|---|---|---|
| **IS**（2010-2018） | 9 | 7.67% | **0.52** | -17.9% | **9.3%** |
| **OOS**（2019-2026） | 7.4 | **21.00%** | **1.03** | -13.5% | **76.7%** |
| Full（2010-2026） | 16.4 | 13.63% | 0.78 | -17.6% | 38.7% |

**两个关键观察**：

1. **OOS > IS** Sharpe 翻一倍。这是**经典 overfitting 的反方向**（overfitting 表现为 IS >> OOS）。

2. **OOS PSR 暴涨**：IS PSR 9.3% 意味着 2010-2018 几乎没有真 alpha 的统计证据。OOS PSR 76.7% 意味着 2019-2026 有强证据。

**解读**：2010-2018 是长单向牛市，跨资产 rotation 增值有限。2019-2026 包含 COVID crash（2020）、2022 熊市、2023-25 rotation——**regime-shift 环境是本策略发光的地方**。

**风险**：如果未来 5-10 年类似 2010-2018（长牛低 vol），策略在绝对收益上跑输 SPY。这种 regime 下 forward Sharpe 约 0.5。

---

## 5. SOXX 敏感性（QC cloud）

SOXX（半导体）约 26% 月份在 top 4。**担忧**：2017-2024 半导体超级周期是否拉高了结果。

| Universe | CAGR | Sharpe | MDD | PSR |
|---|---|---|---|---|
| U11（含 SOXX） | 13.63% | **0.778** | -17.6% | 38.7% |
| **U10（去 SOXX）** | 9.45% | **0.539** | -17.9% | 11.2% |
| **去 SOXX 的 Δ** | **-4.18 pp** | **-0.239** | -0.3 pp | -27.5 pp |

**SOXX 贡献约 0.24 Sharpe**（占 full Sharpe 的 31%）。本地 yfinance 估计是 0.27——两个方法一致。

**没有 SOXX，策略跑输 SPY**（Sharpe 0.54 vs 0.86）。U10 本质上是"分散的债券/黄金 rotation 加一些股票暴露"——防御型但不击败市场。

**风险**：如果半导体超级周期结束（如 2026+ 半导体周期见顶、AI capex 放缓），策略失去关键 alpha。**监控 SOXX pick 频率：超过 40% 月份是红色警报**。

---

## 6. 仓位集中度（long_n）扫描——QC cloud

| 配置 | CAGR | Sharpe | MDD | PSR | 最终 $100k |
|---|---|---|---|---|---|
| n=2（最集中） | **16.19%** | 0.765 | **-24.9%** | 27.4% | $1.17M |
| n=3 | 14.89% | **0.788** | -21.9% | 36.2% | $971k |
| **n=4**（baseline） | 13.63% | 0.778 | **-17.6%** | **38.7%** | $810k |

**权衡**：
- n=2：CAGR 最高（vs n=4 多 +2.6 pp）但 MDD 大很多（+7.3 pp）
- n=3：Sharpe 微胜（vs n=4 多 +0.01），MDD 略大
- **n=4：MDD 最低、PSR 最高、最简单执行**

**选 n=4 的理由**：
- MDD 17.6% 在 $20k 起始账户上心理可承受
- PSR 38.7% 最高——统计上最可辩护
- 较低 turnover → 较少 tax drag（taxable 账户相关）

如果用户能承受 -25% drawdown 且追求高 CAGR，n=2 或 n=3 是有效替代。

---

## 7. Weighting scheme——QC cloud

| Scheme | CAGR | Sharpe | MDD | 备注 |
|---|---|---|---|---|
| **Rank**（40/30/20/10） | 13.63% | **0.778** | -17.6% | top pick 拿 bottom pick 的 4 倍 |
| Equal（每个 25%） | 11.76% | 0.687 | **-16.3%** | 4 个 picks 同权重 |

**Rank 胜出**：
- +1.87 pp CAGR
- +0.09 Sharpe
- 代价：+1.3 pp MDD（可接受）

本地 yfinance 之前显示 rank > equal 约 0.06 Sharpe。QC 确认且差距略大（+0.09）。

---

## 8. Local yfinance vs QC cloud——为什么数字不同

本地 prototyping（yfinance + 自定义 Python simulator）一直显示比 QC cloud 更高 Sharpe 和更低 MDD：

| 指标 | Local yfinance | QC cloud | Δ |
|---|---|---|---|
| CAGR | 14.30% | 13.63% | -0.67 pp |
| Sharpe | 1.20 | 0.78 | **-0.42** |
| MDD | -15.6% | -17.6% | -2.0 pp |

**差异来源**：

1. **本地未建模佣金 + GST** —— QC 在 16 年里 $100k 仓位收了 $1,275。绝对值小但累积。
2. **本地未建模滑点** —— QC 应用 5 bp 单边 = 每 trade 约 10 bp。800 trades 累积是可测量的拖累。
3. **数据 adjustments** —— yfinance 用 Yahoo 自动调整价格；QC 用 Quandl/IEX feeds，split/dividend 处理略不同。
4. **Sharpe 公式细节** —— QC 的 Sharpe 包含年化 conventions，可能跟简单的 `mean/std × sqrt(252)` 略有差异。

**含义**：**forward 期望以 QC 数字为准**。本地 yfinance 的 Sharpe 1.20 是 prototype 级——对在 100+ 配置里做方向选择有用，但不是真实的 backtest。

---

## 9. Forward 期望（重新校准）

锚定 QC 数字，**不**是本地 yfinance：

| 指标 | QC baseline | **现实 forward** | 理由 |
|---|---|---|---|
| Sharpe | 0.78 | **0.5 - 0.7** | 过去 16 年 Sharpe 在实施中通常 degrade 20-40%（cost/slippage 估计、regime shift） |
| CAGR | 13.6% | **9 - 12%** | 未来 5-10 年预期类似 regime；SOXX 周期风险打折 |
| Max drawdown | -17.6% | **-20% 到 -28%** | 新 regime 可能有更大 drawdown；CSC stress（如 2008 风格）未充分测试 |
| Win rate（月度） | 75% | **55 - 65%** | 高 win rate 看起来依赖 momentum regime |

**历史 backtest 没充分演练的关键 edge case**：
- 2008 风格跨资产 crash（所有主要资产类别同时跌 30%+）。我们 16 年从 2010-Q1 开始。
- 多年 stagflation（1970s）——sample 只有 2022 两个 quarter 的轻度 inflation
- 持续 5+ 年低 vol 牛市（2013-2016、2017 是这种——策略在 IS 表现差）

---

## 10. Diagnostic D——IWM 排除理由

之前在 QC cloud 上（3d_xsmom_lo project 里）测试过加/移除 IWM（小盘 ETF）：

| Universe | Sharpe | MDD |
|---|---|---|
| 含 IWM（原 6-ETF） | 0.90 | -25.5% |
| 不含 IWM（5-ETF） | **1.00** | **-22.9%** |

IWM 在 14-16% 月份被选中且一直 underperform。**小盘股不分享大盘 momentum 动态**（Fama-French 2012 发现：小盘 momentum 比大盘 IC 弱）。U11 故意排除 IWM。

---

## 11. DCA 对比（$20k 起始 + $3k/月）——local sim

对于初投 $20k + 每月 $3k 投入 11.4 年（总存入 $429k）的人：

| 场景 | 最终资金 | 存入资金 ROI | Max drawdown |
|---|---|---|---|
| **策略 DCA** | ~$2.54M | +317% | **-15%** |
| SPY DCA | $2.43M | +300% | -33% |
| QQQ DCA | $4.10M | +575% | -34% |

策略 DCA 比 SPY DCA 多约 $110k，回撤只一半。输 QQQ DCA 超过 $1.5M 但回撤控制好得多。

⚠️ 此 DCA 分析在发现 QC 较低 Sharpe 之前本地跑（yfinance）。**实际 forward DCA 结果可能是这些数字的 70-85%**，由于 cost。

---

## 12. 16 年 pick 频率（QC full backtest）

QC backtest 的 800 个订单（约 200 月度 rebalance）：

| Ticker | ~Pick 频率 | 角色 |
|---|---|---|
| GLD | 45% | 避险锚 |
| TLT | 40% | 长久期 play |
| **SOXX** | **26%** | Equity beta（关键贡献者） |
| DBC | 23% | 商品 |
| QQQ | 20% | 科技 beta |
| VNQ | 17% | 实物资产 |
| IEF | 12% | 中等久期 |
| EFA | 4% | 国际 |
| HYG | 4% | 信用 |
| VWO | 3% | 新兴 |
| SPY | 1% | 几乎不被选 vs 其他资产类别 |

**洞察**：债券 + 黄金 主导长期 picks。SOXX 选择性捕捉 equity 上行。SPY 几乎不被选——它的广市场 beta 被更集中的替代品压制。

**策略真在 rotation**：16 年里 25 个不同 top-2 pairs，同 pair 最长连续只 11 个月。

---

## 13. 已知限制和 caveats

1. **多重检验偏差**：最终配置在探索 100+ 变体后浮现。即使有 IS/OOS 切分，post-2018 知识泄露到 universe/参数选择不可避免。

2. **SOXX 依赖**：31% Sharpe 来自 SOXX。如果半导体周期反转，单板块集中风险。

3. **滑点假设**：5 bp 可能低估了较不流动 ETF（VWO、HYG）的实际滑点。真实 fills 可能比 backtest 差 5-10 bp。

4. **Tax inefficient**：月度调仓产生频繁短期 gains。美国 taxable 账户的 post-tax returns 会显著低于 backtest（可能 -3 pp/yr）。

5. **Regime 敏感性**：策略在 regime-shift 市场最有效。在持续低 vol 牛市（如 2010-2018 IS），Sharpe 跌到约 0.5。

6. **数据质量**：yfinance prototype 用 Yahoo 数据；QC 用 Quandl/IEX。调整价格的一些发散是正常的。

7. **生存者偏差**：所有 11 个 universe 资产到 2026 都还在交易。如果选过一个退市的 ETF，hindsight 偏差就缺席——但我们故意选了 well-known 的流动品种。

---

## 14. 手动执行

见 `manual/monthly_rebalance.ipynb`。Workflow：
1. 每月第一个交易日，填入当前 IBKR 持仓 + 现金
2. 跑所有 cells（用 yfinance 算实时信号）
3. 输出是准备好 IBKR market orders 的交易清单
4. 决策 log 自动保存到 `rebalance_log_YYYY-MM-DD.txt`

预计执行时间：每月 3-5 分钟。

---

## 15. 持续运营决策点

**何时不要相信策略**：
- 在全新 regime 中实施（如 2025+ 可能跟 2015-2024 的 momentum 动态截然不同）
- 如果 SOXX 连续 12+ 个月出现在 top-4 超过 50% 月份——策略已退化为单板块 bet
- 如果 forward Sharpe 持续 6+ 个月低于 0.4——暂停并重新评估

**何时考虑加码**：
- 6+ 个月 paper trading，实现 Sharpe 接近 backtest 期望（0.5+）
- 没有单一资产占长期 P&L attribution 50% 以上
- 实盘体验的 MDD 在 forward 期望内（-28% 阈值）

**定期 review**：
- 季度：检查 pick 频率 vs backtest 分布（Section 12）
- 年度：用新一年数据 append 后完整重跑 QC backtest
- **永远**：永远不要基于近期结果重新 tune universe 或参数——那是 overfitting

---

## 16. 一句话总结

> **风险控制的 equity overlay**：U11 跨资产 momentum rotation 配 rank weighting，在 QC cloud 上 2010-2026 实现大致 SPY-相当的 Sharpe（0.78），回撤只有 SPY 的一半（-17.6% vs -33.7%）。策略价值集中在 regime-shift 期（OOS 2019-2026 Sharpe 1.03），在长单向牛市挣扎（IS 2010-2018 Sharpe 0.52）。约 31% Sharpe 来自 SOXX 参与——已知集中风险。现实 forward Sharpe 0.5-0.7，CAGR 9-12%，MDD -20% 到 -28%。每月通过 `manual/monthly_rebalance.ipynb` notebook 手动执行。

---

## 17. 决策 log

| 日期 | 决策 | 理由 |
|---|---|---|
| 2026-05-16 | 策略 v1 = U11 + residual_mom + n=4 + rank | QC backtest 扫描里 risk-adjusted 最佳配置。n=4 优于 n=3 是因为 MDD；rank > equal weighting 0.09 Sharpe |
| 2026-05-16 | 放弃 IWM，放弃 XOM，放弃 USO，没有 BTC sleeve | 按 Diagnostic D（IWM 伤害），以及用户偏好将 BTC 在策略外手动处理 |

---

## 18. 相关 artifacts

- **Trading notebook**：`manual/monthly_rebalance.ipynb`
- **QC 策略代码**：`strategies/3d_xsmom_v2/`（cloud-id `31740853`）
- **项目 spec**：`docs/research_plan.md`
- **Diagnostic 脚本**（本地 prototyping，研究期间在 `/tmp/`，未 commit）：
  - `robustness_tests.py` —— IC、子段、regime、跨资产
  - `deep_dive.py` —— range market、SOXX、IWM、QQQ IC stability
  - `universe_concentration_sweep.py` —— 3 universes × 4 n × 2 signals
  - `weighting_sweep.py` —— 4 weight schemes × 4 n × 2 universes × 3 periods
  - `btc_sleeve_xom.py` —— BTC sleeve sizing + XOM/USO/XLE 对比
  - `diagnostics.py` —— SOXX 敏感性、集中度、clean OOS 验证
