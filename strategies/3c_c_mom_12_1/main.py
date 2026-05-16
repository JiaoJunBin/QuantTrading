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


class Combo3C_C_Mom121(QCAlgorithm):
    """
    Phase 3C-C. Daily SPY long-term momentum (Jegadeesh-Titman 12-1).

    Phase 2C found mom_12_1 (12-month return excluding the most recent month)
    has IC = +0.089 at 63-day forward horizon. This is the only price-based
    signal that survived as momentum rather than reversion — short-term moves
    revert but year-over-year trend continues.

    Entry: rolling-quantile threshold on the last `quantile_window` days of
           mom_12_1 values. Long when in top `1 - quantile_pct`, short when
           in bottom `quantile_pct`.
    Exit:  fixed `holding_days` or ATR-multiple stop.
    """

    def initialize(self):
        self.set_start_date(2020, 1, 1)
        self.set_end_date(2026, 5, 15)
        self.set_cash(100_000)
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

        self.quantile_pct    = float(self.get_parameter("quantile_pct")    or 0.20)
        self.quantile_window = int(self.get_parameter("quantile_window")   or 126)
        self.holding_days    = int(self.get_parameter("holding_days")      or 63)
        self.atr_stop        = float(self.get_parameter("atr_stop")        or 4.0)

        self.spy = self.add_equity("SPY", Resolution.DAILY).symbol
        sec = self.securities[self.spy]
        sec.set_fee_model(IBKRSingaporeFeeModel())
        sec.set_slippage_model(ConstantSlippageModel(0.0005))

        self.atr_ind = self.atr(self.spy, 14)

        # Need 253 close prices to compute mom_12_1 at day t:
        #   price[t-21] / price[t-252] - 1
        # RollingWindow[0] is the most recent; we index back to position 252.
        self.price_history = RollingWindow[float](253)
        self.mom_history   = RollingWindow[float](self.quantile_window)

        self.set_warm_up(timedelta(days=300 + self.quantile_window + 30))

        self.entry_price = None
        self.days_in_pos = 0

    def on_data(self, slice):
        if not self.atr_ind.is_ready:
            return
        if self.spy not in slice.bars:
            return

        bar = slice.bars[self.spy]
        self.price_history.add(float(bar.close))

        if not self.price_history.is_ready:
            return

        # Jegadeesh-Titman 12-1: skip the most recent 21 days, look at 252-21 = 231-day move
        price_skip_1m  = self.price_history[21]
        price_minus_12 = self.price_history[252]
        mom_12_1 = price_skip_1m / price_minus_12 - 1
        self.mom_history.add(float(mom_12_1))

        if self.is_warming_up or not self.mom_history.is_ready:
            return

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

        moms = [self.mom_history[i] for i in range(self.mom_history.count)]
        q_lo = float(np.percentile(moms, self.quantile_pct * 100))
        q_hi = float(np.percentile(moms, (1 - self.quantile_pct) * 100))

        if mom_12_1 > q_hi:
            self.set_holdings(self.spy, 1.0)
            self.entry_price = bar.close
            self.days_in_pos = 0
        elif mom_12_1 < q_lo:
            self.set_holdings(self.spy, -1.0)
            self.entry_price = bar.close
            self.days_in_pos = 0
