# region imports
from AlgorithmImports import *
# endregion


class IBKRSingaporeFeeModel(FeeModel):
    def get_order_fee(self, parameters):
        quantity = abs(parameters.order.absolute_quantity)
        commission = max(0.35, quantity * 0.0035) + 0.10
        return OrderFee(CashAmount(commission * 1.09, "USD"))


class Combo3E_TSMom(QCAlgorithm):
    """
    Time-series momentum on 6 ETFs (Moskowitz Ooi Pedersen 2012).

    Per-asset rule rather than cross-sectional ranking. Each asset gets an
    independent long-or-cash decision based on its OWN 12-1 momentum.
    Equal weight 1/N on each asset that qualifies. Cash on the rest.

    Differences from 3d_xsmom_lo cross-sectional:
        - All 6 assets can be long simultaneously when all have positive
          momentum. lo would only hold top 2.
        - If only 1 asset has positive momentum, TSM allocates only 1/6
          weight to it. lo would allocate 50 percent (1/long_n).
        - TSM scales smoothly with the number of positive-momentum assets;
          lo concentrates regardless.
    """

    def initialize(self):
        self.set_start_date(2020, 1, 1)
        self.set_end_date(2026, 5, 15)
        self.set_cash(100_000)
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

        tickers = ["SPY", "QQQ", "IWM", "EFA", "TLT", "GLD"]
        self.symbols = []
        for t in tickers:
            sym = self.add_equity(t, Resolution.DAILY).symbol
            self.symbols.append(sym)
            sec = self.securities[sym]
            sec.set_fee_model(IBKRSingaporeFeeModel())
            sec.set_slippage_model(ConstantSlippageModel(0.0005))

        self.price_history = {sym: RollingWindow[float](253) for sym in self.symbols}
        self.set_warm_up(timedelta(days=400))

        self.schedule.on(
            self.date_rules.month_start(self.symbols[0]),
            self.time_rules.at(10, 0),
            self.rebalance,
        )

    def on_data(self, slice):
        for sym in self.symbols:
            if sym in slice.bars:
                self.price_history[sym].add(float(slice.bars[sym].close))

    def rebalance(self):
        if self.is_warming_up:
            return

        N = len(self.symbols)
        weight = 1.0 / N    # 1/6 each when fully invested

        target = {sym: 0.0 for sym in self.symbols}
        for sym in self.symbols:
            ph = self.price_history[sym]
            if not ph.is_ready or ph[252] <= 0:
                continue
            mom = ph[21] / ph[252] - 1
            if mom > 0:
                target[sym] = weight

        for sym, w in target.items():
            self.set_holdings(sym, w)

        moms = {sym: (self.price_history[sym][21] / self.price_history[sym][252] - 1)
                for sym in self.symbols if self.price_history[sym].is_ready}
        ranks_str = " ".join(f"{sym.value}={mom:+.3f}" for sym, mom in moms.items())
        picks = [sym.value for sym, w in target.items() if w > 0]
        self.log(f"tsmom picks={' '.join(picks) if picks else 'CASH'} signals {ranks_str}")
