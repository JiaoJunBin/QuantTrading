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


class Combo3D_XSMom_V3(QCAlgorithm):
    """
    Phase 3D v3. Long-only cross-asset momentum with vol targeting on an
    expanded 11-ETF universe.

    Enhancements over v2 (long-only on 6 ETFs, equal weight, Sharpe 0.53):
        1. Universe 6 -> 11 ETFs spanning US equity styles, international,
           rates, credit, gold, commodities, REITs.
        2. long_n 2 -> 3 (still about top quartile of universe).
        3. Vol targeting at target_vol annualized. Each rebalance, scale
           gross exposure by target_vol / SPY 20-day realized vol, capped
           at leverage_cap.

    The vol overlay is approximate. It uses SPY realized vol as a portfolio
    vol proxy. When SPY vol is high (crisis), leverage drops below 1, taking
    risk off. When low (calm), leverage goes above 1 up to the cap.
    """

    def initialize(self):
        # Date range (overridable for IS/OOS splits).
        start_str = self.get_parameter("start_date") or "2020-01-01"
        end_str   = self.get_parameter("end_date")   or "2026-05-15"
        sy, sm, sd = map(int, start_str.split("-"))
        ey, em, ed = map(int, end_str.split("-"))
        self.set_start_date(sy, sm, sd)
        self.set_end_date(ey, em, ed)
        self.set_cash(100_000)
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

        self.long_n       = int(self.get_parameter("long_n")       or 3)
        self.target_vol   = float(self.get_parameter("target_vol")   or 0.15)
        self.leverage_cap = float(self.get_parameter("leverage_cap") or 1.5)

        tickers = [
            "SPY", "QQQ", "IWM",        # US equity styles
            "EFA", "VWO",                # International developed and emerging
            "TLT", "IEF", "HYG",         # Long bonds medium bonds high yield credit
            "GLD", "DBC",                # Gold and broad commodities
            "VNQ",                       # US REITs
        ]
        self.symbols = []
        for t in tickers:
            sym = self.add_equity(t, Resolution.DAILY).symbol
            self.symbols.append(sym)
            sec = self.securities[sym]
            sec.set_fee_model(IBKRSingaporeFeeModel())
            sec.set_slippage_model(ConstantSlippageModel(0.0005))

        self.price_history = {sym: RollingWindow[float](253) for sym in self.symbols}
        self.set_warm_up(timedelta(days=400))

        # symbols[0] is SPY (first in list). Anchor rebalance to its calendar.
        self.schedule.on(
            self.date_rules.month_start(self.symbols[0]),
            self.time_rules.at(10, 0),
            self.rebalance,
        )

    def on_data(self, slice):
        for sym in self.symbols:
            if sym in slice.bars:
                self.price_history[sym].add(float(slice.bars[sym].close))

    def _spy_realized_vol(self) -> float:
        """20-day annualized realized vol of SPY as portfolio-vol proxy."""
        ph = self.price_history[self.symbols[0]]
        if ph.count < 21:
            return 0.15
        prices = [ph[i] for i in range(21)]
        returns = [prices[i] / prices[i + 1] - 1 for i in range(20)]
        return float(np.std(returns) * np.sqrt(252))

    def rebalance(self):
        if self.is_warming_up:
            return

        moms = {}
        for sym in self.symbols:
            ph = self.price_history[sym]
            if not ph.is_ready:
                continue
            p_skip = ph[21]
            p_back = ph[252]
            if p_back > 0:
                moms[sym] = p_skip / p_back - 1

        if not moms:
            return

        positive = {sym: m for sym, m in moms.items() if m > 0}
        winners  = sorted(positive.items(), key=lambda kv: -kv[1])[:self.long_n]
        winner_syms = {sym for sym, _ in winners}

        spy_vol = self._spy_realized_vol()
        leverage = min(self.target_vol / max(spy_vol, 0.05), self.leverage_cap)

        weight = leverage / self.long_n
        target = {sym: 0.0 for sym in self.symbols}
        for sym in winner_syms:
            target[sym] = weight

        for sym, w in target.items():
            self.set_holdings(sym, w)

        all_ranked = sorted(moms.items(), key=lambda kv: -kv[1])
        ranks_str = " ".join(f"{sym.value}={mom:+.3f}" for sym, mom in all_ranked)
        picks_str = " ".join(sym.value for sym in winner_syms) if winners else "CASH"
        self.log(f"rebalance lev={leverage:.2f} spyvol={spy_vol:.3f} picks={picks_str} ranks {ranks_str}")
