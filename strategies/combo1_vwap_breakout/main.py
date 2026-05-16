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


class Combo1VWAPBreakout(QCAlgorithm):
    """
    Phase 3 — Combo 1' (pivoted from spec's mean-reversion design).

    Empirical Phase 2 finding: vwap_deviation has positive IC at intraday horizons
    (1-2h), with the signal concentrated in the top quantile. The spec's
    "deviation below threshold → mean revert" hypothesis was contradicted by data.

    Entry  : close above intraday VWAP by an amount that ranks in the top
             `quantile_threshold` (default 80%) of the last `quantile_window` bars,
             AND current 15-min volume is at least `volume_multiplier` × the
             trailing 20-bar mean.
    Exit   : ATR-based stop, fixed bars held, or 15:45 ET strict liquidate.
    Holding: ~1.5h intraday, no overnight.
    """

    def initialize(self):
        # ── date range and capital ─────────────────────────────────────────────
        self.set_start_date(2022, 1, 1)
        self.set_end_date(2024, 12, 31)
        self.set_cash(100_000)
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

        # ── parameters (overridable via QC optimization) ───────────────────────
        self.quantile_threshold = float(self.get_parameter("quantile_threshold") or 0.80)
        self.quantile_window    = int(self.get_parameter("quantile_window")    or 100)
        self.volume_multiplier  = float(self.get_parameter("volume_multiplier") or 1.3)
        self.atr_stop           = float(self.get_parameter("atr_stop")          or 2.0)
        self.holding_bars       = int(self.get_parameter("holding_bars")       or 6)     # 6 × 15min = 1.5h
        self.skip_open_minutes  = int(self.get_parameter("skip_open_minutes")  or 30)

        # ── universe ───────────────────────────────────────────────────────────
        self.spy = self.add_equity("SPY", Resolution.MINUTE).symbol
        sec = self.securities[self.spy]
        sec.set_fee_model(IBKRSingaporeFeeModel())
        sec.set_slippage_model(ConstantSlippageModel(0.0005))

        # ── indicators ─────────────────────────────────────────────────────────
        # VWAP: built-in, daily-reset, fed by minute bars
        self.vwap_ind = self.vwap(self.spy)
        # ATR: manual, fed by 15-min consolidated bars
        self.atr_ind = AverageTrueRange(14)

        # ── rolling history for quantile and volume baseline ──────────────────
        self.dev_history    = RollingWindow[float](self.quantile_window)
        self.volume_history = RollingWindow[float](20)

        # ── 15-min consolidator ────────────────────────────────────────────────
        self.cons = TradeBarConsolidator(timedelta(minutes=15))
        self.cons.data_consolidated += self.on_15min_bar
        self.subscription_manager.add_consolidator(self.spy, self.cons)

        # ── warmup: enough minute bars to fill 100-bar 15-min history + ATR ───
        self.set_warm_up(timedelta(days=10))

        # ── state ──────────────────────────────────────────────────────────────
        self.entry_price = None
        self.bars_in_pos = 0

    def on_15min_bar(self, sender, bar):
        # 1. update manual indicators
        self.atr_ind.update(bar)

        # 2. record history
        if self.vwap_ind.is_ready:
            dev = (bar.close - self.vwap_ind.current.value) / self.vwap_ind.current.value
            self.dev_history.add(float(dev))
        else:
            dev = None
        self.volume_history.add(float(bar.volume))

        if self.is_warming_up:
            return
        if not (self.dev_history.is_ready and self.volume_history.is_ready
                and self.atr_ind.is_ready and dev is not None):
            return

        # 3. day-end strict liquidate at 15:45 ET (before close)
        end_t = bar.end_time
        if end_t.hour == 15 and end_t.minute == 45:
            if self.portfolio[self.spy].invested:
                self.liquidate(self.spy)
                self.entry_price = None
                self.bars_in_pos = 0
            return

        # 4. skip the first N minutes after the open (noisy auction prints)
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

        # 6. entry signal
        devs = [self.dev_history[i] for i in range(self.dev_history.count)]
        threshold = float(np.percentile(devs, self.quantile_threshold * 100))
        avg_vol = sum(self.volume_history) / self.volume_history.count

        if dev > threshold and bar.volume > avg_vol * self.volume_multiplier:
            self.set_holdings(self.spy, 1.0)
            self.entry_price = bar.close
            self.bars_in_pos = 0
