# region imports
from AlgorithmImports import *
# endregion


class IBKRSingaporeFeeModel(FeeModel):
    """IBKR Pro Tiered ($0.0035/share, min $0.35) + $0.10 venue fee + 9% Singapore GST."""

    def get_order_fee(self, parameters):
        quantity = abs(parameters.order.absolute_quantity)
        commission = max(0.35, quantity * 0.0035) + 0.10
        return OrderFee(CashAmount(commission * 1.09, "USD"))


class Combo2OBVTrend(QCAlgorithm):
    """
    Phase 3 — Combo 2 (per spec, supported by Phase 2 IC).

    Trades trend continuation when OBV breaks a rolling extreme AND price agrees AND
    volume confirms. Exits Donchian-style: long position closes when price drops to
    the rolling N/2-bar minimum (or hits ATR stop). Symmetric for shorts.

    Holding period can span multiple days — no day-end forced liquidate. This is
    the only Phase 3 combo allowed to hold overnight, per spec §2.2.
    """

    def initialize(self):
        # ── date range and capital ─────────────────────────────────────────────
        self.set_start_date(2022, 1, 1)
        self.set_end_date(2024, 12, 31)
        self.set_cash(100_000)
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

        # ── parameters ─────────────────────────────────────────────────────────
        self.obv_lookback_in   = int(self.get_parameter("obv_lookback_in")   or 60)   # entry breakout window
        self.exit_lookback     = int(self.get_parameter("exit_lookback")     or 20)   # Donchian exit window
        self.volume_multiplier = float(self.get_parameter("volume_multiplier") or 1.3)
        self.atr_stop          = float(self.get_parameter("atr_stop")          or 2.0)

        # ── universe ───────────────────────────────────────────────────────────
        self.spy = self.add_equity("SPY", Resolution.MINUTE).symbol
        sec = self.securities[self.spy]
        sec.set_fee_model(IBKRSingaporeFeeModel())
        sec.set_slippage_model(ConstantSlippageModel(0.0005))

        # ── indicators (manual, fed by 15-min consolidator) ───────────────────
        self.obv_ind = OnBalanceVolume()
        self.atr_ind = AverageTrueRange(14)

        # ── rolling history ────────────────────────────────────────────────────
        # Need max(lookback_in, exit_lookback) + slack. Use lookback_in+1 so we
        # can exclude the current bar from the breakout reference.
        history_len = max(self.obv_lookback_in, self.exit_lookback) + 1
        self.obv_history    = RollingWindow[float](history_len)
        self.price_history  = RollingWindow[float](history_len)
        self.volume_history = RollingWindow[float](20)

        # ── 15-min consolidator ────────────────────────────────────────────────
        self.cons = TradeBarConsolidator(timedelta(minutes=15))
        self.cons.data_consolidated += self.on_15min_bar
        self.subscription_manager.add_consolidator(self.spy, self.cons)

        # ── warmup ─────────────────────────────────────────────────────────────
        self.set_warm_up(timedelta(days=10))

        # ── state ──────────────────────────────────────────────────────────────
        self.entry_price = None

    def on_15min_bar(self, sender, bar):
        # 1. update indicators with the new 15-min bar
        self.obv_ind.update(bar)
        self.atr_ind.update(bar)

        if not (self.obv_ind.is_ready and self.atr_ind.is_ready):
            return

        # 2. record history (skipped during warmup so first non-warmup bar is real)
        self.obv_history.add(float(self.obv_ind.current.value))
        self.price_history.add(float(bar.close))
        self.volume_history.add(float(bar.volume))

        if self.is_warming_up:
            return
        if not (self.obv_history.is_ready and self.price_history.is_ready
                and self.volume_history.is_ready):
            return

        current_obv   = self.obv_history[0]
        current_price = self.price_history[0]
        atr           = self.atr_ind.current.value

        # 3. rolling extrema (exclude current bar — index 0)
        obv_window   = [self.obv_history[i]   for i in range(1, self.obv_lookback_in + 1)]
        price_window = [self.price_history[i] for i in range(1, self.obv_lookback_in + 1)]
        exit_window  = [self.price_history[i] for i in range(1, self.exit_lookback + 1)]
        avg_vol      = sum(self.volume_history) / self.volume_history.count

        holding = self.portfolio[self.spy]

        # 4. position management
        if holding.invested:
            if holding.is_long:
                stop_hit = current_price < self.entry_price - self.atr_stop * atr
                donchian_exit = current_price < min(exit_window)
                if stop_hit or donchian_exit:
                    self.liquidate(self.spy)
                    self.entry_price = None
            elif holding.is_short:
                stop_hit = current_price > self.entry_price + self.atr_stop * atr
                donchian_exit = current_price > max(exit_window)
                if stop_hit or donchian_exit:
                    self.liquidate(self.spy)
                    self.entry_price = None
            return

        # 5. entry signal
        volume_ok = bar.volume > avg_vol * self.volume_multiplier
        if (current_obv > max(obv_window)
                and current_price > max(price_window)
                and volume_ok):
            self.set_holdings(self.spy, 1.0)
            self.entry_price = current_price
        elif (current_obv < min(obv_window)
                and current_price < min(price_window)
                and volume_ok):
            self.set_holdings(self.spy, -1.0)
            self.entry_price = current_price
