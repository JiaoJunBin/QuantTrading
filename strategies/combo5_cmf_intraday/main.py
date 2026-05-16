# region imports
from AlgorithmImports import *
import numpy as np
# endregion


class IBKRSingaporeFeeModel(FeeModel):
    """IBKR Pro Tiered ($0.0035/share, min $0.35) + $0.10 venue fee + 9% Singapore GST."""

    def get_order_fee(self, parameters):
        quantity = abs(parameters.order.absolute_quantity)
        commission = max(0.35, quantity * 0.0035) + 0.10
        return OrderFee(CashAmount(commission * 1.09, "USD"))


class Combo5CMFIntraday(QCAlgorithm):
    """
    Phase 3 — Combo 5 (new, not in spec; data-driven).

    Phase 2 finding: Chaikin Money Flow had the strongest single intraday IC
    of all tested indicators (~0.052, verdict "good") at the 2-hour horizon.
    The top quantile of CMF showed the largest forward returns across SPY/QQQ/IWM.

    Entry  : CMF in the top `quantile_threshold` (default 80%) of the rolling
             `quantile_window` bars, AND close exceeds the rolling
             `breakout_lookback`-bar high (price + flow confirmation).
    Exit   : ATR-based stop, fixed bars held (default 8 = 2h), or 15:45 ET liquidate.
    Holding: ~2h intraday, no overnight.
    """

    def initialize(self):
        # ── date range and capital ─────────────────────────────────────────────
        self.set_start_date(2022, 1, 1)
        self.set_end_date(2024, 12, 31)
        self.set_cash(100_000)
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

        # ── parameters ─────────────────────────────────────────────────────────
        self.quantile_threshold = float(self.get_parameter("quantile_threshold") or 0.80)
        self.quantile_window    = int(self.get_parameter("quantile_window")     or 100)
        self.breakout_lookback  = int(self.get_parameter("breakout_lookback")   or 8)
        self.cmf_period         = int(self.get_parameter("cmf_period")          or 20)
        self.atr_stop           = float(self.get_parameter("atr_stop")           or 2.0)
        self.holding_bars       = int(self.get_parameter("holding_bars")        or 8)   # 2h
        self.skip_open_minutes  = int(self.get_parameter("skip_open_minutes")   or 30)

        # ── universe ───────────────────────────────────────────────────────────
        self.spy = self.add_equity("SPY", Resolution.MINUTE).symbol
        sec = self.securities[self.spy]
        sec.set_fee_model(IBKRSingaporeFeeModel())
        sec.set_slippage_model(ConstantSlippageModel(0.0005))

        # ── indicators (manual, fed by 15-min consolidator) ───────────────────
        self.cmf_ind = ChaikinMoneyFlow(self.cmf_period)
        self.atr_ind = AverageTrueRange(14)

        # ── rolling history ────────────────────────────────────────────────────
        self.cmf_history    = RollingWindow[float](self.quantile_window)
        # Need breakout_lookback+1 prices so we can exclude current bar from the high.
        self.price_history  = RollingWindow[float](self.breakout_lookback + 1)

        # ── 15-min consolidator ────────────────────────────────────────────────
        self.cons = TradeBarConsolidator(timedelta(minutes=15))
        self.cons.data_consolidated += self.on_15min_bar
        self.subscription_manager.add_consolidator(self.spy, self.cons)

        # ── warmup ─────────────────────────────────────────────────────────────
        self.set_warm_up(timedelta(days=10))

        # ── state ──────────────────────────────────────────────────────────────
        self.entry_price = None
        self.bars_in_pos = 0

    def on_15min_bar(self, sender, bar):
        # 1. update manual indicators
        self.cmf_ind.update(bar)
        self.atr_ind.update(bar)

        if not (self.cmf_ind.is_ready and self.atr_ind.is_ready):
            return

        # 2. record history
        self.cmf_history.add(float(self.cmf_ind.current.value))
        self.price_history.add(float(bar.close))

        if self.is_warming_up:
            return
        if not (self.cmf_history.is_ready and self.price_history.is_ready):
            return

        end_t = bar.end_time

        # 3. day-end strict liquidate at 15:45 ET
        if end_t.hour == 15 and end_t.minute == 45:
            if self.portfolio[self.spy].invested:
                self.liquidate(self.spy)
                self.entry_price = None
                self.bars_in_pos = 0
            return

        # 4. skip first N minutes after open
        market_open = end_t.replace(hour=9, minute=30, second=0, microsecond=0)
        if (end_t - market_open).total_seconds() / 60.0 < self.skip_open_minutes:
            return

        holding = self.portfolio[self.spy]

        # 5. position management
        if holding.invested:
            self.bars_in_pos += 1
            atr = self.atr_ind.current.value
            if bar.close < self.entry_price - self.atr_stop * atr:
                self.liquidate(self.spy)
                self.entry_price = None
                self.bars_in_pos = 0
            elif self.bars_in_pos >= self.holding_bars:
                self.liquidate(self.spy)
                self.entry_price = None
                self.bars_in_pos = 0
            return

        # 6. entry signal: CMF in top quantile AND price > N-bar high (excluding current)
        cmfs = [self.cmf_history[i] for i in range(self.cmf_history.count)]
        threshold = float(np.percentile(cmfs, self.quantile_threshold * 100))
        recent_high = max(self.price_history[i] for i in range(1, self.breakout_lookback + 1))
        current_cmf = self.cmf_history[0]

        if current_cmf > threshold and bar.close > recent_high:
            self.set_holdings(self.spy, 1.0)
            self.entry_price = bar.close
            self.bars_in_pos = 0
