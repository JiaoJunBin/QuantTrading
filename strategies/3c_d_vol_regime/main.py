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


class Combo3C_D_VolRegime(QCAlgorithm):
    """
    Phase 3C-D. Daily SPY vol-regime continuation, long-only.

    Phase 2C found realized_vol (annualized 20-day return stddev) has
    IC = +0.144 at 21-day forward horizon. Interpretation: high recent vol
    is compensated by higher forward returns (vol risk premium). The signal
    is consistent across bull and range regimes.

    Long-only because the symmetric short (low vol implies low return) is
    economically dubious and tends to short long stretches of grinding-up
    bull markets — a known failure mode.

    Entry: rolling-quantile threshold on the last `quantile_window` days of
           realized_vol. Long when in top `1 - quantile_pct`. Hold for
           `holding_days` or stop out.
    """

    def initialize(self):
        self.set_start_date(2020, 1, 1)
        self.set_end_date(2026, 5, 15)
        self.set_cash(100_000)
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

        self.quantile_pct    = float(self.get_parameter("quantile_pct")    or 0.20)
        self.quantile_window = int(self.get_parameter("quantile_window")   or 126)
        self.holding_days    = int(self.get_parameter("holding_days")      or 21)
        self.vol_period      = int(self.get_parameter("vol_period")        or 20)
        self.atr_stop        = float(self.get_parameter("atr_stop")        or 3.0)

        self.spy = self.add_equity("SPY", Resolution.DAILY).symbol
        sec = self.securities[self.spy]
        sec.set_fee_model(IBKRSingaporeFeeModel())
        sec.set_slippage_model(ConstantSlippageModel(0.0005))

        self.atr_ind = self.atr(self.spy, 14)

        # Need vol_period + 1 prices to compute vol_period daily returns
        self.price_history  = RollingWindow[float](self.vol_period + 1)
        self.vol_history    = RollingWindow[float](self.quantile_window)

        self.set_warm_up(timedelta(days=self.vol_period + self.quantile_window + 30))

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

        # Realized vol: annualized stddev of last vol_period daily returns
        prices = [self.price_history[i] for i in range(self.price_history.count)]
        returns = [prices[i] / prices[i + 1] - 1 for i in range(len(prices) - 1)]
        realized_vol = float(np.std(returns) * np.sqrt(252))
        self.vol_history.add(realized_vol)

        if self.is_warming_up or not self.vol_history.is_ready:
            return

        atr = self.atr_ind.current.value
        holding = self.portfolio[self.spy]

        if holding.invested:
            self.days_in_pos += 1
            stop_long = holding.is_long and bar.close < self.entry_price - self.atr_stop * atr
            if stop_long or self.days_in_pos >= self.holding_days:
                self.liquidate(self.spy)
                self.entry_price = None
                self.days_in_pos = 0
            return

        vols = [self.vol_history[i] for i in range(self.vol_history.count)]
        q_hi = float(np.percentile(vols, (1 - self.quantile_pct) * 100))

        if realized_vol > q_hi:
            self.set_holdings(self.spy, 1.0)
            self.entry_price = bar.close
            self.days_in_pos = 0
