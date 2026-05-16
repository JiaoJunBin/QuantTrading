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


class Combo3D_XSMom_V2(QCAlgorithm):
    """
    Phase 3D v2. Cross-asset momentum on 11 ETFs, residual_mom signal, rank weighting.

    Hardcoded best-config from local diagnostic sweep:
      Universe   U11 = SPY, QQQ, EFA, TLT, GLD, VWO, HYG, VNQ, IEF, DBC, SOXX
      Signal     residual_mom (12-1 momentum stripped of beta to SPY)
      Selection  top 4 by signal among positives
      Weighting  rank weighted 40 30 20 10 percent
      Rebalance  monthly first trading day
    """

    UNIVERSE = ["SPY", "QQQ", "EFA", "TLT", "GLD",
                "VWO", "HYG", "VNQ", "IEF", "DBC", "SOXX"]
    LONG_N = 4
    RANK_WEIGHTS = [4.0, 3.0, 2.0, 1.0]   # 40 30 20 10 percent

    def initialize(self):
        # Date range — overridable for IS/OOS splits
        start_str = self.get_parameter("start_date") or "2010-01-04"
        end_str   = self.get_parameter("end_date")   or "2026-05-15"
        sy, sm, sd = map(int, start_str.split("-"))
        ey, em, ed = map(int, end_str.split("-"))
        self.set_start_date(sy, sm, sd)
        self.set_end_date(ey, em, ed)

        starting_cash = float(self.get_parameter("starting_cash") or 100_000)
        self.set_cash(starting_cash)
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

        self.symbols = []
        for t in self.UNIVERSE:
            sym = self.add_equity(t, Resolution.DAILY).symbol
            self.symbols.append(sym)
            sec = self.securities[sym]
            sec.set_fee_model(IBKRSingaporeFeeModel())
            sec.set_slippage_model(ConstantSlippageModel(0.0005))

        # 253 closes lets us compute price t-21 over price t-252 plus 231-day residual window
        self.price_history = {sym: RollingWindow[float](253) for sym in self.symbols}

        # Warmup so 252-day windows are filled by start_date
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

    def _residual_mom(self, sym):
        """Cumulative residual return after stripping SPY beta from the asset.
        Uses returns over the 231-day window ending 21 days ago."""
        ph = self.price_history[sym]
        spy_ph = self.price_history[self.symbols[0]]
        if not ph.is_ready or not spy_ph.is_ready:
            return None
        try:
            if sym == self.symbols[0]:
                # SPY against itself just use plain 12-1
                return ph[21] / ph[252] - 1
            sym_rets = [ph[i] / ph[i + 1] - 1 for i in range(21, 252)]
            spy_rets = [spy_ph[i] / spy_ph[i + 1] - 1 for i in range(21, 252)]
            if len(sym_rets) < 30:
                return None
            cov = float(np.cov(sym_rets, spy_rets, ddof=0)[0, 1])
            var = float(np.var(spy_rets, ddof=0))
            beta = cov / var if var > 1e-10 else 1.0
            return float(sum(sr - beta * spr for sr, spr in zip(sym_rets, spy_rets)))
        except (ZeroDivisionError, ValueError):
            return None

    def _rank_weights(self, winners):
        """Rank-weighted allocation. winners is list of (sym, signal) sorted descending."""
        k = len(winners)
        if k == 0:
            return {}
        raw = self.RANK_WEIGHTS[:k]
        total = sum(raw)
        deployed = k / self.LONG_N
        return {sym: (raw[i] / total) * deployed for i, (sym, _) in enumerate(winners)}

    def rebalance(self):
        if self.is_warming_up:
            return

        signals = {}
        for sym in self.symbols:
            s = self._residual_mom(sym)
            if s is not None:
                signals[sym] = s

        if not signals:
            return

        positives = sorted([(s, v) for s, v in signals.items() if v > 0],
                           key=lambda kv: -kv[1])[:self.LONG_N]
        weights = self._rank_weights(positives)

        target = {sym: weights.get(sym, 0.0) for sym in self.symbols}
        for sym, w in target.items():
            self.set_holdings(sym, w)

        ranked = sorted(signals.items(), key=lambda kv: -kv[1])
        ranks_str = " ".join(f"{s.value}={v:+.3f}" for s, v in ranked)
        picks_str = " ".join(f"{s.value}@{weights[s]*100:.0f}%" for s, _ in positives) if positives else "CASH"
        self.log(f"rebalance picks={picks_str} ranks {ranks_str}")
