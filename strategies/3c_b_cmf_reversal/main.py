# region imports
from AlgorithmImports import *
import numpy as np
# endregion


class IBKRSingaporeFeeModel(FeeModel):
    """IBKR Pro Tiered + venue + 9% Singapore GST."""

    def get_order_fee(self, parameters):
        quantity = abs(parameters.order.absolute_quantity)
        commission = max(0.35, quantity * 0.0035) + 0.10
        return OrderFee(CashAmount(commission * 1.09, "USD"))


class Combo3C_B_CMFReversal(QCAlgorithm):
    """
    Phase 3C-B. Daily SPY mean reversion based on Chaikin Money Flow.

    Phase 2C found cmf_20 has IC = -0.201 at 63-day forward horizon (strongest
    single daily signal). Money-flow extremes mean-revert over the next quarter.

    Entry: rolling-quantile threshold on the last `quantile_window` days of
           cmf_20 values. Long when in bottom `quantile_pct`, short when in
           top `1 - quantile_pct`.
    Exit:  fixed `holding_days` (~ 1 quarter) or ATR-multiple stop.
    """

    def initialize(self):
        self.set_start_date(2020, 1, 1)
        self.set_end_date(2026, 5, 15)
        self.set_cash(100_000)
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

        self.quantile_pct    = float(self.get_parameter("quantile_pct")    or 0.20)
        self.quantile_window = int(self.get_parameter("quantile_window")   or 126)
        self.holding_days    = int(self.get_parameter("holding_days")      or 63)
        self.cmf_period      = int(self.get_parameter("cmf_period")        or 20)
        self.atr_stop        = float(self.get_parameter("atr_stop")        or 4.0)

        self.spy = self.add_equity("SPY", Resolution.DAILY).symbol
        sec = self.securities[self.spy]
        sec.set_fee_model(IBKRSingaporeFeeModel())
        sec.set_slippage_model(ConstantSlippageModel(0.0005))

        self.cmf_ind = self.cmf(self.spy, self.cmf_period, Resolution.DAILY)
        self.atr_ind = self.atr(self.spy, 14)

        self.cmf_history = RollingWindow[float](self.quantile_window)

        self.set_warm_up(timedelta(days=self.cmf_period + self.quantile_window + 30))

        self.entry_price = None
        self.days_in_pos = 0

    def on_data(self, slice):
        if not (self.cmf_ind.is_ready and self.atr_ind.is_ready):
            return
        if self.spy not in slice.bars:
            return

        bar = slice.bars[self.spy]
        self.cmf_history.add(float(self.cmf_ind.current.value))

        if self.is_warming_up or not self.cmf_history.is_ready:
            return

        cmf_now = self.cmf_history[0]
        atr = self.atr_ind.current.value
        holding = self.portfolio[self.spy]

        if holding.invested:
            self.days_in_pos += 1
            stop_long  = holding.is_long  and bar.close < self.entry_price - self.atr_stop * atr
            stop_short = holding.is_short and bar.close > self.entry_price + self.atr_stop * atr
            if stop_long or stop_short or self.days_in_pos >= self.holding_days:
                self.liquidate(self.spy)
                self.entry_price = None
                self.days_in_pos = 0
            return

        cmfs = [self.cmf_history[i] for i in range(self.cmf_history.count)]
        q_lo = float(np.percentile(cmfs, self.quantile_pct * 100))
        q_hi = float(np.percentile(cmfs, (1 - self.quantile_pct) * 100))

        if cmf_now < q_lo:
            self.set_holdings(self.spy, 1.0)
            self.entry_price = bar.close
            self.days_in_pos = 0
        elif cmf_now > q_hi:
            self.set_holdings(self.spy, -1.0)
            self.entry_price = bar.close
            self.days_in_pos = 0
