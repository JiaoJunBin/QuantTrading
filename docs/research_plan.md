# 量价指标组合研究与回测项目

> 这是一份给 Claude Code 的工程任务文档。目标是在 QuantConnect 平台上系统化研究和验证基于量价关系的交易策略。

---

## 1. 项目背景

### 1.1 目标
构建并验证 3-4 个基于量价关系的策略组合,覆盖**趋势确认、均值回归、突破捕捉、Order Flow** 4 个不同方向。每个策略需经过严谨的因子有效性验证(IC、分组测试)和回测(out-of-sample),最终输出一份对比报告。

### 1.2 交易对象
- **市场**:美股
- **核心标的**:SPY、QQQ(必须)、IWM、DIA(可选扩展)
- **时间粒度**:15 分钟 bar(部分指标需要用分钟数据聚合)
- **持仓周期**:几小时到几天(intraday 到 short-term swing)

### 1.3 平台和工具
- **回测平台**:QuantConnect Cloud(Free tier 即可)
- **本地开发**:LEAN CLI(需 Quant Researcher Seat)
- **语言**:Python
- **代码版本管理**:本地 git,推 GitHub 私人仓库

### 1.4 项目目录结构
```
quant-dev/
├── research/                          # 研究 notebook
│   ├── 01_data_exploration.ipynb     # 数据探索
│   ├── 02_indicator_analysis.ipynb   # 单指标 IC 分析
│   └── 03_combo_validation.ipynb     # 组合验证
├── strategies/                        # 策略代码(LEAN 项目)
│   ├── combo1_vwap_volume/
│   ├── combo2_obv_breakout/
│   ├── combo3_mfi_meanrev/
│   └── combo4_volume_climax/
├── analysis/                          # 分析工具
│   ├── ic_calculator.py
│   ├── quantile_test.py
│   └── backtest_comparator.py
├── reports/                           # 输出报告
│   └── strategy_comparison.md
└── README.md
```

---

## 2. 推荐的 4 个指标组合

每个组合的设计原则:**主信号 + 量能过滤 + 风控/出场**。避免单一维度堆叠。

### 2.1 组合 1:VWAP 偏离 + 成交量异常(均值回归)

**核心逻辑**:价格大幅偏离日内 VWAP 后,在量能放大确认下做均值回归。

**信号定义**:
```
入场(做多):
  - 价格 < VWAP × (1 - threshold)         # 默认 threshold = 0.005 (0.5%)
  - 当前 15min bar 成交量 > 当日同时段平均 × 1.5
  - 不是当日前 30 分钟(避免开盘噪音)

入场(做空):
  - 价格 > VWAP × (1 + threshold)
  - 成交量条件同上

出场:
  - 价格回到 VWAP ±0.001 范围内
  - 或日内强平(15:55 ET)
  - 或止损:ATR(14) × 2
```

**参数列表**:
- `vwap_threshold`: 0.003, 0.005, 0.008
- `volume_multiplier`: 1.2, 1.5, 2.0
- `atr_stop_multiplier`: 1.5, 2.0, 3.0
- `skip_minutes_after_open`: 30, 60

**预期表现**:夏普 0.8-1.5,胜率 55-65%,平均持仓几小时

---

### 2.2 组合 2:OBV 突破 + 成交量确认(趋势跟随)

**核心逻辑**:OBV 突破历史高低点确认资金流方向,叠加成交量放大确认。

**信号定义**:
```
入场(做多):
  - OBV 突破过去 N bar 最高值
  - 当前 bar 成交量 > 过去 20 bar 平均 × 1.5
  - 价格也突破过去 N bar 最高(确认价量同步)

入场(做空):
  - OBV 跌破过去 N bar 最低值
  - 同样的量能和价格确认

出场:
  - 价格跌破 N/2 bar 内最低(做多)或突破最高(做空)— Donchian 风格
  - 或 OBV 反向突破
  - 或止损 ATR(14) × 2
```

**参数列表**:
- `obv_lookback`: 20, 40, 60
- `exit_lookback`: 10, 20
- `volume_multiplier`: 1.3, 1.5, 2.0

**预期表现**:夏普 0.5-1.2,胜率 40-50% 但盈亏比 > 2

---

### 2.3 组合 3:MFI 极值反转 + 价量背离(均值回归)

**核心逻辑**:MFI(资金流量指数)进入极值区域 + 价量背离作为反转信号。

**信号定义**:
```
入场(做多):
  - MFI(14) < 20(超卖)
  - 价格创近 N bar 新低,但 MFI 未创新低(底背离)
  - 量能未恶化:当前 bar volume 不超过过去 20 bar 平均 × 1.5

入场(做空):
  - MFI(14) > 80(超买)
  - 价格创近 N bar 新高,但 MFI 未创新高(顶背离)

出场:
  - MFI 回到 40-60 中性区
  - 或时间止损(持仓 > 8 bar 自动平)
  - 或止损 ATR(14) × 1.5
```

**参数列表**:
- `mfi_period`: 14, 21
- `oversold_threshold`: 15, 20, 25
- `divergence_lookback`: 10, 20

**预期表现**:胜率较高(60%+)但单次盈利较小,适合配合趋势策略对冲

---

### 2.4 组合 4:Volume Climax 反转(高级)

**核心逻辑**:检测异常巨量(可能是恐慌/狂热的极端点),配合 K 线形态做反向操作。

**信号定义**:
```
检测 Climax bar:
  - 当前 bar volume > 过去 50 bar 平均 × 3.0
  - 当前 bar 波幅 > 过去 14 bar 平均波幅 × 2.0
  - 收盘价位于 K 线高/低 25% 区域(强方向感)

入场(做多 — 卖盘 climax):
  - 检测到 climax + 收盘在 K 线下 25%
  - 等待下一个 bar 不再创新低
  - 入场

入场(做空 — 买盘 climax):
  - 检测到 climax + 收盘在 K 线上 25%
  - 等待下一个 bar 不再创新高
  - 入场

出场:
  - 持仓 4 个 bar 后平仓(快进快出)
  - 或止损 ATR(14) × 1.0(严格止损,因为反转策略)
```

**参数列表**:
- `volume_climax_multiplier`: 2.5, 3.0, 4.0
- `range_multiplier`: 1.5, 2.0, 2.5
- `holding_bars`: 3, 4, 6

**预期表现**:胜率 50-60%,信号稀疏(一年几十次),单次盈亏比好

---

## 3. 验证方法

每个指标组合在投入回测前,**必须**经过以下验证流程。流程严谨度从机构量化研究借鉴。

### 3.1 步骤 1:单指标 IC 分析

**目的**:验证每个指标本身是否有预测力。

**计算逻辑**:
```python
# 伪代码
indicator_value = calculate_indicator(price, volume, ...)
future_return_1d = price.pct_change().shift(-1)
future_return_5d = price.pct_change(5).shift(-5)

ic_1d = indicator_value.corr(future_return_1d)
ic_5d = indicator_value.corr(future_return_5d)

# Rolling IC,看时间稳定性
rolling_ic = indicator_value.rolling(60).corr(future_return_1d)
```

**判断标准**:
- |IC| < 0.02:指标无效,放弃
- 0.02 ≤ |IC| < 0.05:边际有效,需要组合
- 0.05 ≤ |IC| < 0.10:不错
- |IC| ≥ 0.10:很好(警惕过拟合)

**Rolling IC 稳定性**:
- 60 bar 滚动 IC 标准差 / 均值 < 1.5:稳定
- IC 在不同月份正负符号一致:方向稳定

### 3.2 步骤 2:分组测试(Quantile Test)

**目的**:验证指标值和未来收益的**单调关系**。

```python
# 把指标值分成 5 档
indicator_rank = indicator_value.rank(pct=True)
quantile = pd.cut(indicator_rank, 5, labels=False)

# 看每档的平均未来收益
for q in range(5):
    avg_ret = future_return_1d[quantile == q].mean()
    std_ret = future_return_1d[quantile == q].std()
    n = (quantile == q).sum()
    print(f"Q{q}: avg={avg_ret:.4f}, std={std_ret:.4f}, n={n}")
```

**判断标准**:
- 好指标:Q1 到 Q5 收益**单调变化**(递增或递减)
- 坏指标:各组收益接近 / 无序

### 3.3 步骤 3:稳健性测试

#### 3.3.1 参数敏感性

把核心参数 ±20% 扫一遍,看回测指标变化:

```python
for vwap_threshold in [0.003, 0.004, 0.005, 0.006, 0.007]:
    for volume_multi in [1.2, 1.5, 1.8, 2.0]:
        result = backtest(vwap_threshold, volume_multi)
        # 记录 Sharpe、MDD、Total Return
```

**判断**:相邻参数组合的 Sharpe 应该平滑变化,不应有"悬崖"。**悬崖式表现是过拟合的信号**。

#### 3.3.2 时间段稳定性(Walk-forward Analysis)

把回测期分成多段,**只用前段调参,后段验证**:

```
2018-2019:  In-sample(调参)
2020-2021:  Out-of-sample(验证 1)
2022-2023:  Out-of-sample(验证 2)
2024-2025:  Out-of-sample(验证 3)
```

**判断**:OOS 表现应该达到 IS 的 60-80%。如果 OOS 比 IS 好,你可能在 IS 上调参不够;如果 OOS 远低于 IS,你过拟合了。

#### 3.3.3 不同市场环境分析

把回测期按市场环境分类:
- **牛市**(SPY 年化 > 15%):2019, 2021, 2023, 2024
- **熊市**(SPY 年化 < -10%):2022(部分)
- **震荡市**:其他

分别看策略在每个环境下的表现。**理想策略应该有可解释的"擅长环境"**。

### 3.4 步骤 4:完整回测

#### 4.1 回测设置
```python
# QC 框架
self.set_start_date(2020, 1, 1)
self.set_end_date(2024, 12, 31)
self.set_cash(100_000)
self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

# 重要:Singapore IBKR GST 9% 要建模(自定义 fee model)
class IBKRSingaporeFeeModel(FeeModel):
    def get_order_fee(self, parameters):
        commission = max(0.35, abs(parameters.order.quantity) * 0.0035)
        # 加 GST 9%
        return OrderFee(CashAmount(commission * 1.09, "USD"))

security.set_fee_model(IBKRSingaporeFeeModel())
```

#### 4.2 关键评估指标

**必须输出的指标**:
- **Total Return**(总收益)
- **CAGR**(年化收益率)
- **Sharpe Ratio**(夏普,目标 > 1.0)
- **Sortino Ratio**(下行风险调整)
- **Max Drawdown**(最大回撤,目标 < 20%)
- **Calmar Ratio**(年化收益 / 最大回撤)
- **Win Rate**(胜率)
- **Profit Factor**(盈利总额 / 亏损总额)
- **Avg Win / Avg Loss**(盈亏比)
- **Total Trades**(总交易次数)
- **Annual Turnover**(年化换手率,了解成本)
- **PSR**(Probabilistic Sharpe Ratio)

**对比基准**:Buy and Hold SPY。

#### 4.3 必须做的细节

- **滑点建模**:用 QC 默认的 `ConstantSlippageModel(slippage_percent=0.0005)`(0.05%)
- **佣金建模**:IBKR Pro Tiered + GST 9%(见上)
- **保证金建模**:Margin 账户,不超过 1.5x 杠杆
- **数据预热**:`set_warm_up(N)` 至少覆盖最长指标周期

### 3.5 步骤 5:组合表现分析

最终把 4 个组合放一起对比:

| 维度 | Buy&Hold | 组合 1 | 组合 2 | 组合 3 | 组合 4 |
|---|---|---|---|---|---|
| CAGR | | | | | |
| Sharpe | | | | | |
| MDD | | | | | |
| Win Rate | | | | | |
| Profit Factor | | | | | |
| Trades/Year | | | | | |
| 牛市表现 | | | | | |
| 熊市表现 | | | | | |
| 震荡市表现 | | | | | |

**找出**:
- 哪些组合**互补**(不同市场环境下表现互补)?
- 是否值得**等权组合**它们形成一个 portfolio?
- 哪个组合的 PSR 最高(最不可能是运气)?

---

## 4. 代码实现框架

### 4.1 Research Notebook 框架

`research/02_indicator_analysis.ipynb`

```python
# 1. 准备环境
from QuantConnect.Research import QuantBook
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

qb = QuantBook()

# 2. 拉数据
symbols = ["SPY", "QQQ", "IWM"]
securities = {s: qb.add_equity(s, Resolution.MINUTE).symbol for s in symbols}

# 拉 3 年分钟数据,聚合到 15min
end = qb.time
start = end - timedelta(days=365 * 3)
history = qb.history(list(securities.values()), start, end, Resolution.MINUTE)

# 聚合到 15min
def resample_to_15min(df):
    return df.groupby(level=0).resample('15min', level=1).agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum'
    }).dropna()

bars_15m = resample_to_15min(history)

# 3. 计算指标
def calc_vwap(df):
    typical = (df['high'] + df['low'] + df['close']) / 3
    return (typical * df['volume']).groupby(df.index.date).cumsum() / \
           df['volume'].groupby(df.index.date).cumsum()

def calc_obv(df):
    direction = np.sign(df['close'].diff())
    return (direction * df['volume']).cumsum()

# ... 其他指标

# 4. IC 计算
def calculate_ic(indicator, returns, periods=[1, 5, 20]):
    results = {}
    for n in periods:
        future_ret = returns.shift(-n)
        ic = indicator.corr(future_ret)
        results[f'IC_{n}d'] = ic
    return results

# 5. 分组测试
def quantile_test(indicator, returns, n_quantiles=5):
    indicator_rank = indicator.rank(pct=True)
    quantile = pd.cut(indicator_rank, n_quantiles, labels=False)
    return returns.groupby(quantile).agg(['mean', 'std', 'count'])

# 6. 输出报告
# 把所有指标的 IC、分组测试、稳健性图表输出
```

### 4.2 策略代码模板

`strategies/combo1_vwap_volume/main.py`

```python
from AlgorithmImports import *

class VWAPVolumeReversion(QCAlgorithm):

    def initialize(self):
        # 时间和资金
        self.set_start_date(2020, 1, 1)
        self.set_end_date(2024, 12, 31)
        self.set_cash(100_000)
        
        # 标的
        self.spy = self.add_equity("SPY", Resolution.MINUTE).symbol
        
        # 券商和费用模型
        self.set_brokerage_model(
            BrokerageName.INTERACTIVE_BROKERS_BROKERAGE,
            AccountType.MARGIN
        )
        security = self.securities[self.spy]
        security.set_fee_model(IBKRSingaporeFeeModel())
        security.set_slippage_model(ConstantSlippageModel(0.0005))
        
        # 参数(暴露为可优化)
        self.vwap_threshold = self.get_parameter("vwap_threshold", 0.005)
        self.volume_multiplier = self.get_parameter("volume_multiplier", 1.5)
        self.atr_stop = self.get_parameter("atr_stop", 2.0)
        self.skip_open_minutes = int(self.get_parameter("skip_open_minutes", 30))
        
        # 指标
        self.vwap = self.vwap(self.spy)
        self.atr = self.atr(self.spy, 14, Resolution.MINUTE)
        
        # 15min consolidator
        self.consolidator = TradeBarConsolidator(timedelta(minutes=15))
        self.consolidator.data_consolidated += self.on_15min_bar
        self.subscription_manager.add_consolidator(self.spy, self.consolidator)
        
        # 滚动窗口存历史成交量(同时段平均)
        self.volume_history = RollingWindow[float](20)
        
        # 预热
        self.set_warm_up(timedelta(days=2))
        
        # 进场价格(用于止损)
        self.entry_price = None

    def on_15min_bar(self, sender, bar):
        if self.is_warming_up:
            return
        
        # 跳过开盘 N 分钟
        time = bar.end_time
        market_open = time.replace(hour=9, minute=30, second=0)
        if (time - market_open).total_seconds() < self.skip_open_minutes * 60:
            return
        
        # 收集成交量历史
        self.volume_history.add(float(bar.volume))
        if not self.volume_history.is_ready:
            return
        
        avg_volume = sum(self.volume_history) / self.volume_history.count
        
        # 信号判断
        price = bar.close
        vwap = self.vwap.current.value
        atr = self.atr.current.value
        
        deviation = (price - vwap) / vwap
        volume_spike = bar.volume > avg_volume * self.volume_multiplier
        
        # 入场逻辑
        if not self.portfolio[self.spy].invested:
            if deviation < -self.vwap_threshold and volume_spike:
                self.set_holdings(self.spy, 1.0)
                self.entry_price = price
                self.log(f"LONG @ {price}, VWAP={vwap}, dev={deviation:.4f}")
            elif deviation > self.vwap_threshold and volume_spike:
                self.set_holdings(self.spy, -1.0)
                self.entry_price = price
                self.log(f"SHORT @ {price}, VWAP={vwap}, dev={deviation:.4f}")
        
        # 出场逻辑
        else:
            holding = self.portfolio[self.spy]
            
            # 止损
            if holding.is_long and price < self.entry_price - atr * self.atr_stop:
                self.liquidate(self.spy)
                self.log(f"STOP LOSS LONG @ {price}")
            elif holding.is_short and price > self.entry_price + atr * self.atr_stop:
                self.liquidate(self.spy)
                self.log(f"STOP LOSS SHORT @ {price}")
            
            # 均值回归到 VWAP
            elif abs(deviation) < 0.001:
                self.liquidate(self.spy)
                self.log(f"MEAN REVERSION EXIT @ {price}")
        
        # 日内强平(15:55 ET)
        if time.hour == 15 and time.minute >= 55:
            if self.portfolio[self.spy].invested:
                self.liquidate(self.spy)
                self.log(f"EOD LIQUIDATE @ {price}")


class IBKRSingaporeFeeModel(FeeModel):
    """IBKR Pro Tiered + Singapore GST 9%"""
    def get_order_fee(self, parameters):
        quantity = abs(parameters.order.absolute_quantity)
        # Tiered: $0.0035/share, min $0.35
        commission = max(0.35, quantity * 0.0035)
        # Add exchange fees estimate (~$0.10/order for low-volume)
        commission += 0.10
        # Add GST 9%
        commission *= 1.09
        return OrderFee(CashAmount(commission, "USD"))
```

### 4.3 IC 分析工具

`analysis/ic_calculator.py`

```python
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

class ICAnalyzer:
    """计算和可视化因子的 IC"""
    
    def __init__(self, indicator: pd.Series, prices: pd.Series):
        self.indicator = indicator
        self.prices = prices
        self.returns = prices.pct_change()
    
    def ic(self, forward_periods=[1, 5, 20]):
        """计算不同前瞻期的 IC"""
        results = {}
        for n in forward_periods:
            future_ret = self.returns.shift(-n)
            valid = self.indicator.notna() & future_ret.notna()
            corr, pval = stats.spearmanr(
                self.indicator[valid], 
                future_ret[valid]
            )
            results[f'{n}d'] = {'ic': corr, 'pvalue': pval, 'n': valid.sum()}
        return results
    
    def rolling_ic(self, window=60, forward_period=1):
        """滚动 IC,看时间稳定性"""
        future_ret = self.returns.shift(-forward_period)
        return self.indicator.rolling(window).corr(future_ret)
    
    def quantile_test(self, n_quantiles=5, forward_period=1):
        """分组测试"""
        future_ret = self.returns.shift(-forward_period)
        ranks = self.indicator.rank(pct=True)
        quantiles = pd.cut(ranks, n_quantiles, labels=False)
        
        grouped = future_ret.groupby(quantiles)
        return pd.DataFrame({
            'mean': grouped.mean(),
            'std': grouped.std(),
            'count': grouped.count(),
            't_stat': grouped.mean() / (grouped.std() / np.sqrt(grouped.count())),
        })
    
    def plot_summary(self):
        """画出 IC 摘要图"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        # 1. Rolling IC
        rolling = self.rolling_ic()
        axes[0,0].plot(rolling.index, rolling.values)
        axes[0,0].axhline(0, color='red', linestyle='--', alpha=0.5)
        axes[0,0].set_title('60-day Rolling IC')
        axes[0,0].set_ylabel('IC')
        
        # 2. IC histogram
        axes[0,1].hist(rolling.dropna(), bins=30)
        axes[0,1].axvline(0, color='red', linestyle='--')
        axes[0,1].set_title('Rolling IC Distribution')
        
        # 3. Quantile test
        qt = self.quantile_test()
        axes[1,0].bar(qt.index, qt['mean'])
        axes[1,0].set_title('Quantile Test (avg future return)')
        axes[1,0].set_xlabel('Quantile')
        axes[1,0].set_ylabel('Avg Return')
        
        # 4. Cumulative return by quantile
        # ...
        
        plt.tight_layout()
        return fig
```

---

## 5. 交付物清单

完成项目后,应输出以下文件:

### 5.1 必交付

1. **`research/01_data_exploration.ipynb`** — 数据探索和基础统计
2. **`research/02_indicator_analysis.ipynb`** — 每个指标的 IC、分组测试、稳健性
3. **`research/03_combo_validation.ipynb`** — 组合策略的验证
4. **`strategies/combo[1-4]_*/main.py`** — 4 个策略的完整 LEAN 代码
5. **`analysis/ic_calculator.py`** — 可复用的因子分析工具
6. **`reports/strategy_comparison.md`** — 最终对比报告(含表格、图表)

### 5.2 可选交付

7. `analysis/walk_forward.py` — Walk-forward 分析工具
8. `analysis/parameter_optimizer.py` — 参数优化框架
9. `strategies/portfolio_combined/` — 4 个策略的组合版本

### 5.3 报告内容(`reports/strategy_comparison.md`)

应该包含:

- 每个组合的 IC 表(1d、5d、20d 前瞻)
- 每个组合的回测表(CAGR、Sharpe、MDD、Win Rate 等)
- 不同市场环境下的表现拆解(牛市/熊市/震荡市)
- Walk-forward 验证结果
- 参数敏感性热力图
- Equity curve 对比图
- 最终推荐:**哪个策略实盘最值得部署,在什么条件下**

---

## 6. 技术注意事项

### 6.1 时间对齐

- QC 的 minute bar 是 ET 时区,要注意夏令时
- VWAP 是按日重置的(每天 9:30 ET 开始累积)
- 跨日策略需要 handle 持仓过夜

### 6.2 数据质量

- QC 免费数据:minute resolution,from IEX (单交易所)
- 注意停牌、分红、拆股影响——QC 默认会自动 adjust
- 节假日 / 半日交易 (e.g. 感恩节后)需要特殊处理

### 6.3 性能优化

- 不要在 `on_data` 里做重度计算
- 用 indicator 而不是手动滚动(LEAN indicators 是 incremental 更新的)
- 滚动窗口用 `RollingWindow[float]`,不要用 list

### 6.4 防过拟合

- **In-sample 数据不要超过总数据的 60%**
- **任何参数调整都要在 in-sample 上做,在 out-of-sample 验证**
- **如果调了 5 次参数,实际有效自由度要打折扣(Sharpe Inflation)**
- 报告里必须区分 IS / OOS 表现

### 6.5 量化研究的常见坑

避免以下错误:
- **Look-ahead bias**:用了未来数据(如 next bar 的 open)
- **Survivorship bias**:只用现在还在交易的标的
- **Selection bias**:挑选历史上表现好的标的回测
- **Data mining**:试了 100 种参数组合,只报告最好的(实际上是过拟合)
- **Ignoring transaction costs**:忽略佣金和滑点

---

## 7. 工作流程建议

按这个顺序推进,不要跳步:

```
Phase 1(1 周): 环境搭建 + 数据探索
  ├─ 装好 LEAN CLI(本地)
  ├─ 跑通 Sample Strategy
  ├─ 写 research/01_data_exploration.ipynb
  └─ 熟悉 QuantBook API

Phase 2(2 周): 单指标 IC 分析
  ├─ 实现所有候选指标(VWAP、OBV、MFI、A/D、CMF、Volume Profile 等)
  ├─ 跑 IC 分析,淘汰 |IC| < 0.02 的指标
  ├─ 看分组测试,确认单调性
  └─ 写 research/02_indicator_analysis.ipynb

Phase 3(2-3 周): 4 个策略实现
  ├─ 实现组合 1:VWAP + Volume
  ├─ 实现组合 2:OBV Breakout
  ├─ 实现组合 3:MFI Reversal
  ├─ 实现组合 4:Volume Climax
  └─ 每个先用日线 / 小样本快速验证,再上完整数据

Phase 4(1 周): 严格验证
  ├─ Walk-forward 分析
  ├─ 参数敏感性测试
  ├─ 不同市场环境拆解
  └─ 写 research/03_combo_validation.ipynb

Phase 5(0.5 周): 报告
  └─ 写 reports/strategy_comparison.md

Phase 6(optional): Paper Trading
  ├─ 选最好的 1-2 个策略
  ├─ 部署到 QC paper trading
  └─ 跑 1-2 个月观察
```

---

## 8. 给 Claude Code 的执行原则

1. **先跑通,再优化**:不要一上来就追求完美。先用日线、单一标的把流程跑通,再扩展到分钟级、多标的。

2. **严格 in-sample / out-of-sample 分离**:任何调参都不能用未来数据。

3. **诚实报告负面结果**:如果某个指标 IC 不显著,如实写出来,不要为了"成果"美化。**好策略的关键不是有多 fancy,而是是否在 OOS 上稳健**。

4. **代码要可重复**:固定 random seed,记录所有参数,确保任何人跑你的代码能得到一样结果。

5. **每完成一个 phase,git commit 一次**,commit message 写关键指标。例如:
   ```
   git commit -m "Phase 2: VWAP IC=0.052 (1d), OBV IC=0.038, MFI IC=0.041"
   ```

6. **不确定时,问回原始问题**:某个设计决策犹豫时,回到根本问题——"这个改动能让我更接近 alpha,还是只是让回测曲线变好看?"

---

## 9. 参考资料

### 书籍
- *Advances in Financial Machine Learning*, Marcos López de Prado(IC 分析、Walk-forward 等方法)
- *Quantitative Trading*, Ernest Chan(实战量化入门)
- *Trading Systems and Methods*, Perry Kaufman(指标百科)
- *Trading and Exchanges*, Larry Harris(市场微观结构)

### 在线资源
- QuantConnect Documentation: https://www.quantconnect.com/docs/v2/
- LEAN GitHub: https://github.com/QuantConnect/Lean
- TradingView Pine Script 文档(看量价指标实现参考)

### 学术论文
- Lee & Ready (1991): "Inferring Trade Direction from Intraday Data"
- Easley, López de Prado, O'Hara: VPIN 系列
- Jegadeesh & Titman (1993): 动量效应经典

---

## 10. 结论

这个项目的目标**不是找到圣杯策略**,而是:

1. **建立一套可复用的量化研究工作流**(IC → 分组 → 稳健性 → 回测 → 报告)
2. **客观验证量价指标在美股上的实际价值**
3. **找出至少 1 个 OOS 上稳健、可部署的策略**

如果项目结束发现 4 个组合都不显著,那也是有价值的——你淘汰了一些方向,知道了哪里不能去。**量化的本质是排除法,不是寻找法。**

---

**项目所有者**:JunBin Jiao
**目标完成时间**:6-8 周
**初始投入**:
- QC 订阅:Free tier 起步,Phase 3 后可考虑升级 Researcher Seat($8-10/月)
- IBKR 账户:已有
- 服务器:本地开发即可,paper trading 用 QC 云端
