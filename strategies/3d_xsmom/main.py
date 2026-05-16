# region imports
from AlgorithmImports import *
# endregion


class IBKRSingaporeFeeModel(FeeModel):
    """IBKR Pro Tiered + venue + 9% Singapore GST."""

    def get_order_fee(self, parameters):
        quantity = abs(parameters.order.absolute_quantity)
        commission = max(0.35, quantity * 0.0035) + 0.10
        return OrderFee(CashAmount(commission * 1.09, "USD"))


class Combo3D_XSMom(QCAlgorithm):
    """
    Phase 3D. Cross-sectional momentum on a 6-ETF universe.

    Mechanism: each monthly rebalance, compute Jegadeesh-Titman 12-1 momentum
    for every ETF, rank them, go long the top `long_n` and short the bottom
    `short_n` with equal weight inside each sleeve. The middle gets weight 0.
    With long_n equal to short_n the resulting portfolio is approximately
    dollar-neutral.

    Universe choice (6 ETFs across asset classes):
        SPY  - US large cap
        QQQ  - US tech
        IWM  - US small cap
        EFA  - International developed
        TLT  - Long-duration US Treasuries
        GLD  - Gold

    TLT and GLD have low correlation with equity ETFs, so realized portfolio
    vol drops even before any explicit vol-targeting overlay.
    """

    def initialize(self):
        self.set_start_date(2020, 1, 1)
        self.set_end_date(2026, 5, 15)
        self.set_cash(100_000)
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

        self.long_n  = int(self.get_parameter("long_n")  or 2)
        self.short_n = int(self.get_parameter("short_n") or 2)

        tickers = ["SPY", "QQQ", "IWM", "EFA", "TLT", "GLD"]
        self.symbols = []
        for t in tickers:
            sym = self.add_equity(t, Resolution.DAILY).symbol
            self.symbols.append(sym)
            sec = self.securities[sym]
            sec.set_fee_model(IBKRSingaporeFeeModel())
            sec.set_slippage_model(ConstantSlippageModel(0.0005))

        # 253 closes lets us compute price[t-21] / price[t-252] - 1
        self.price_history = {sym: RollingWindow[float](253) for sym in self.symbols}

        # Warmup so 252-day windows are filled by start_date
        self.set_warm_up(timedelta(days=400))

        # Monthly rebalance anchored to SPY's trading calendar
        self.schedule.on(
            self.date_rules.month_start(self.symbols[0]),
            self.time_rules.at(10, 0),
            self.rebalance,
        )

    def on_data(self, slice):
        # Update price history every bar including during warmup
        for sym in self.symbols:
            if sym in slice.bars:
                self.price_history[sym].add(float(slice.bars[sym].close))

    def rebalance(self):
        if self.is_warming_up:
            return

        moms = {}
        for sym in self.symbols:
            ph = self.price_history[sym]
            if not ph.is_ready:
                continue
            p_skip = ph[21]    # close 21 trading days ago
            p_back = ph[252]   # close 252 trading days ago
            if p_back > 0:
                moms[sym] = p_skip / p_back - 1

        if len(moms) < self.long_n + self.short_n:
            return

        ranked = sorted(moms.items(), key=lambda kv: -kv[1])
        longs  = [sym for sym, _ in ranked[:self.long_n]]
        shorts = [sym for sym, _ in ranked[-self.short_n:]]

        target = {sym: 0.0 for sym in self.symbols}
        long_weight  =  1.0 / self.long_n
        short_weight = -1.0 / self.short_n
        for sym in longs:
            target[sym] = long_weight
        for sym in shorts:
            target[sym] = short_weight

        # Place orders for every symbol so the un-targeted middle exits
        for sym, w in target.items():
            self.set_holdings(sym, w)

        ranks_str = " ".join(f"{sym.value}={mom:+.4f}" for sym, mom in ranked)
        self.log(f"rebalance ranks {ranks_str}")
