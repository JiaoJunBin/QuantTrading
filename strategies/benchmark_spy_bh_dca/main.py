# region imports
from AlgorithmImports import *
# endregion


class IBKRSingaporeFeeModel(FeeModel):
    def get_order_fee(self, parameters):
        quantity = abs(parameters.order.absolute_quantity)
        commission = max(0.35, quantity * 0.0035) + 0.10
        return OrderFee(CashAmount(commission * 1.09, "USD"))


class SPYBuyHoldDCA(QCAlgorithm):
    """SPY full-invest at start plus monthly deposits that immediately go into SPY.

    Models the realistic retail scenario where you commit your starting capital
    to SPY on day one and add fresh capital each month. Direct comparison point
    for the active strategy under the same deposit pattern.
    """

    def initialize(self):
        self.set_start_date(2020, 1, 1)
        self.set_end_date(2026, 5, 15)

        self.set_cash(float(self.get_parameter("starting_cash")  or 20_000))
        self.monthly_deposit = float(self.get_parameter("monthly_deposit") or 3_000)

        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

        self.spy = self.add_equity("SPY", Resolution.DAILY).symbol
        sec = self.securities[self.spy]
        sec.set_fee_model(IBKRSingaporeFeeModel())
        sec.set_slippage_model(ConstantSlippageModel(0.0005))

        self.schedule.on(
            self.date_rules.month_start(self.spy),
            self.time_rules.at(10, 0),
            self.deposit_and_invest,
        )

        self.bought_initial = False

    def on_data(self, slice):
        # First-day full deployment of initial cash.
        if not self.bought_initial and self.spy in slice.bars:
            self.set_holdings(self.spy, 1.0)
            self.bought_initial = True

    def deposit_and_invest(self):
        # Add new cash and immediately re-target 100 percent SPY so the new
        # cash gets deployed.
        self.portfolio.cash_book["USD"].add_amount(self.monthly_deposit)
        self.set_holdings(self.spy, 1.0)
