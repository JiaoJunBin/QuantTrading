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


class Combo3D_XSMom_LO(QCAlgorithm):
    """
    Phase 3D v2. Long-only cross-asset momentum rotation.

    Replaces the v1 long-short design which suffered a 45 percent drawdown
    when forced to short bonds and gold against trending equities. The fix
    is to drop the short sleeve and filter on absolute momentum so the
    strategy is in cash when no asset has positive 12-1 momentum.

    Mechanism (Antonacci-style Dual Momentum):
        - Every month rank the 6 ETFs by Jegadeesh-Titman 12-1 momentum
        - Keep only those with positive momentum
        - Long the top long_n among the survivors equal weight
        - If fewer than long_n have positive momentum hold the rest as cash

    Effect: in a bear market that takes every asset down, the strategy goes
    to cash. In a normal bull market, the strategy concentrates on the
    strongest few assets.
    """

    def initialize(self):
        # Date range (overridable via QC parameter for IS/OOS splits).
        start_str = self.get_parameter("start_date") or "2020-01-01"
        end_str   = self.get_parameter("end_date")   or "2026-05-15"
        sy, sm, sd = map(int, start_str.split("-"))
        ey, em, ed = map(int, end_str.split("-"))
        self.set_start_date(sy, sm, sd)
        self.set_end_date(ey, em, ed)

        # Capital and deposit settings (parameterizable).
        starting_cash         = float(self.get_parameter("starting_cash")   or 100_000)
        self.monthly_deposit  = float(self.get_parameter("monthly_deposit") or 0)
        self.set_cash(starting_cash)
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

        self.long_n      = int(self.get_parameter("long_n") or 2)
        self.freq        = (self.get_parameter("freq") or "monthly").lower()
        # Signal choice. mom_12_1 is the baseline. See _signal for the menu.
        self.signal_type = (self.get_parameter("signal") or "mom_12_1").lower()

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

        # Rebalance schedule depends on freq.
        if self.freq == "weekly":
            self.schedule.on(
                self.date_rules.week_start(self.symbols[0]),
                self.time_rules.at(10, 0),
                self.rebalance,
            )
        elif self.freq == "quarterly":
            self.schedule.on(
                self.date_rules.month_start(self.symbols[0]),
                self.time_rules.at(10, 0),
                self._quarterly_check,
            )
        else:  # monthly default
            self.schedule.on(
                self.date_rules.month_start(self.symbols[0]),
                self.time_rules.at(10, 0),
                self.rebalance,
            )

        # External deposits each month, before the rebalance.
        if self.monthly_deposit > 0:
            self.schedule.on(
                self.date_rules.month_start(self.symbols[0]),
                self.time_rules.at(9, 35),
                self.deposit,
            )

    def on_data(self, slice):
        for sym in self.symbols:
            if sym in slice.bars:
                self.price_history[sym].add(float(slice.bars[sym].close))

    def _quarterly_check(self):
        # Rebalance only at start of Jan / Apr / Jul / Oct.
        if self.time.month in (1, 4, 7, 10):
            self.rebalance()

    def deposit(self):
        if self.is_warming_up:
            return
        self.portfolio.cash_book["USD"].add_amount(self.monthly_deposit)

    def _signal(self, sym):
        """Compute the configured signal for one symbol. Returns float or None."""
        ph = self.price_history[sym]
        if not ph.is_ready:
            return None
        st = self.signal_type
        try:
            if st == "mom_12_1":
                return ph[21] / ph[252] - 1
            if st == "mom_6_1":
                return ph[21] / ph[126] - 1
            if st == "mom_3_1":
                return ph[21] / ph[63] - 1
            if st == "risk_adj_mom":
                mom = ph[21] / ph[252] - 1
                prices = [ph[i] for i in range(21, 253)]
                rets = [prices[i] / prices[i + 1] - 1 for i in range(len(prices) - 1)]
                vol = float(np.std(rets)) * np.sqrt(252)
                return mom / max(vol, 0.01)
            if st == "pct_of_52wk_high":
                prices = [ph[i] for i in range(253)]
                hi = max(prices)
                return prices[0] / hi if hi > 0 else None
            if st == "residual_mom":
                # Strip SPY-market beta from each asset, take cum residual return
                spy_ph = self.price_history[self.symbols[0]]
                if not spy_ph.is_ready:
                    return None
                if sym == self.symbols[0]:
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
        return None

    def _signal_threshold(self):
        """Below-threshold signals are excluded (Antonacci-style absolute filter)."""
        if self.signal_type == "pct_of_52wk_high":
            return 0.85  # within 15 percent of 52-week high
        return 0.0

    def rebalance(self):
        if self.is_warming_up:
            return

        moms = {}
        for sym in self.symbols:
            s = self._signal(sym)
            if s is not None:
                moms[sym] = s

        if not moms:
            return

        # Absolute-strength filter (signal must exceed threshold)
        threshold = self._signal_threshold()
        positive = {sym: m for sym, m in moms.items() if m > threshold}

        # Take top long_n by momentum among the positive survivors
        winners = sorted(positive.items(), key=lambda kv: -kv[1])[:self.long_n]
        winner_syms = {sym for sym, _ in winners}

        # Each winner gets equal share of 100 percent. Un-targeted symbols go to cash.
        weight = 1.0 / self.long_n  # always /long_n, so when fewer than long_n
                                    # qualify the remainder is held as cash
        target = {sym: 0.0 for sym in self.symbols}
        for sym in winner_syms:
            target[sym] = weight

        for sym, w in target.items():
            self.set_holdings(sym, w)

        # Log diagnostics
        all_ranked = sorted(moms.items(), key=lambda kv: -kv[1])
        ranks_str = " ".join(f"{sym.value}={mom:+.3f}" for sym, mom in all_ranked)
        winners_str = " ".join(sym.value for sym in winner_syms) if winners else "CASH"
        self.log(f"rebalance signal={self.signal_type} picks={winners_str} ranks {ranks_str}")
