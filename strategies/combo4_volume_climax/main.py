# region imports
from AlgorithmImports import *
# endregion


class IBKRSingaporeFeeModel(FeeModel):
    """IBKR Pro Tiered ($0.0035/share, min $0.35) + $0.10 venue fee + 9% Singapore GST."""

    def get_order_fee(self, parameters):
        quantity = abs(parameters.order.absolute_quantity)
        commission = max(0.35, quantity * 0.0035) + 0.10
        return OrderFee(CashAmount(commission * 1.09, "USD"))


class Combo4VolumeClimax(QCAlgorithm):
    """
    Phase 3 — Combo 4 (per spec, event-based).

    NOT validated by Phase 2 IC analysis — that framework can't measure rare-event
    detectors. Kept per spec to test the hypothesis that capitulation/euphoria
    bars at extreme volume + range mean-revert on the next bar.

    Climax bar:    volume > volume_mult × 50-bar avg AND range > range_mult × 14-bar avg ATR
                   AND close in the top-25% or bottom-25% of the bar's range.
    Setup:         climax-down (close in bottom 25%) → look to go LONG next bar if no new low.
                   climax-up   (close in top    25%) → look to go SHORT next bar if no new high.
    Hold:          fixed bars (default 4 = 1h). Tight ATR stop (1.0×) since the entry is
                   already at an extreme.
    """

    def initialize(self):
        # ── date range and capital ─────────────────────────────────────────────
        self.set_start_date(2022, 1, 1)
        self.set_end_date(2024, 12, 31)
        self.set_cash(100_000)
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

        # ── parameters ─────────────────────────────────────────────────────────
        self.volume_climax_mult = float(self.get_parameter("volume_climax_mult") or 3.0)
        self.range_mult         = float(self.get_parameter("range_mult")         or 2.0)
        self.holding_bars       = int(self.get_parameter("holding_bars")        or 4)   # 1h
        self.atr_stop           = float(self.get_parameter("atr_stop")           or 1.0) # tight
        self.skip_open_minutes  = int(self.get_parameter("skip_open_minutes")   or 30)

        # ── universe ───────────────────────────────────────────────────────────
        self.spy = self.add_equity("SPY", Resolution.MINUTE).symbol
        sec = self.securities[self.spy]
        sec.set_fee_model(IBKRSingaporeFeeModel())
        sec.set_slippage_model(ConstantSlippageModel(0.0005))

        # ── indicators (manual, fed by consolidator) ──────────────────────────
        self.atr_ind = AverageTrueRange(14)

        # ── rolling history ────────────────────────────────────────────────────
        self.volume_history = RollingWindow[float](50)
        self.range_history  = RollingWindow[float](14)

        # ── 15-min consolidator ────────────────────────────────────────────────
        self.cons = TradeBarConsolidator(timedelta(minutes=15))
        self.cons.data_consolidated += self.on_15min_bar
        self.subscription_manager.add_consolidator(self.spy, self.cons)

        # ── warmup ─────────────────────────────────────────────────────────────
        self.set_warm_up(timedelta(days=10))

        # ── state ──────────────────────────────────────────────────────────────
        self.entry_price = None
        self.bars_in_pos = 0
        # Climax setup, populated when a climax bar is detected, consumed by next bar.
        # Tuple: (direction, climax_high, climax_low) where direction in {'down', 'up'}.
        self.setup = None

    def on_15min_bar(self, sender, bar):
        # 1. update ATR
        self.atr_ind.update(bar)

        # 2. record history BEFORE evaluating signals (so averages exclude current bar)
        prev_volumes = [self.volume_history[i] for i in range(self.volume_history.count)]
        prev_ranges  = [self.range_history[i]  for i in range(self.range_history.count)]
        self.volume_history.add(float(bar.volume))
        self.range_history.add(float(bar.high - bar.low))

        if self.is_warming_up:
            return
        if not (self.atr_ind.is_ready and len(prev_volumes) >= 50 and len(prev_ranges) >= 14):
            return

        end_t = bar.end_time

        # 3. day-end strict liquidate at 15:45 ET, clear any pending setup
        if end_t.hour == 15 and end_t.minute == 45:
            if self.portfolio[self.spy].invested:
                self.liquidate(self.spy)
                self.entry_price = None
                self.bars_in_pos = 0
            self.setup = None
            return

        # 4. skip opening N minutes — climaxes near the open are auction artifacts
        market_open = end_t.replace(hour=9, minute=30, second=0, microsecond=0)
        if (end_t - market_open).total_seconds() / 60.0 < self.skip_open_minutes:
            self.setup = None
            return

        holding = self.portfolio[self.spy]
        atr = self.atr_ind.current.value
        bar_range = bar.high - bar.low

        # 5. position management
        if holding.invested:
            self.bars_in_pos += 1
            stopped_long  = holding.is_long  and bar.close < self.entry_price - self.atr_stop * atr
            stopped_short = holding.is_short and bar.close > self.entry_price + self.atr_stop * atr
            if stopped_long or stopped_short or self.bars_in_pos >= self.holding_bars:
                self.liquidate(self.spy)
                self.entry_price = None
                self.bars_in_pos = 0
            return

        # 6. handle pending setup from previous bar
        if self.setup is not None:
            direction, c_high, c_low = self.setup
            if direction == "down" and bar.low > c_low:
                # bullish: yesterday's panic-sell didn't make a new low → long
                self.set_holdings(self.spy, 1.0)
                self.entry_price = bar.close
                self.bars_in_pos = 0
            elif direction == "up" and bar.high < c_high:
                # bearish: yesterday's FOMO bar didn't make a new high → short
                self.set_holdings(self.spy, -1.0)
                self.entry_price = bar.close
                self.bars_in_pos = 0
            self.setup = None
            return

        # 7. detect a new climax (only when no active setup and no position)
        avg_vol   = sum(prev_volumes) / len(prev_volumes)
        avg_range = sum(prev_ranges)  / len(prev_ranges)
        is_climax = (bar.volume > avg_vol   * self.volume_climax_mult
                     and bar_range > avg_range * self.range_mult)
        if not is_climax or bar_range == 0:
            return
        close_loc = (bar.close - bar.low) / bar_range
        if close_loc <= 0.25:
            self.setup = ("down", float(bar.high), float(bar.low))
        elif close_loc >= 0.75:
            self.setup = ("up", float(bar.high), float(bar.low))
