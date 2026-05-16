# region imports
from AlgorithmImports import *
# endregion


class IBKRSingaporeFeeModel(FeeModel):
    def get_order_fee(self, parameters):
        quantity = abs(parameters.order.absolute_quantity)
        commission = max(0.35, quantity * 0.0035) + 0.10
        return OrderFee(CashAmount(commission * 1.09, "USD"))


class BenchmarkSPYDCA(QCAlgorithm):
    """Dollar-cost average into SPY.

    Initial 100k held as cash. Every month invest a fixed slice into SPY at
    the open. After all 77 monthly deposits the entire 100k is fully invested
    in SPY. Compare against lump-sum and against active strategies.
    """

    def initialize(self):
        self.set_start_date(2020, 1, 1)
        self.set_end_date(2026, 5, 15)
        self.set_cash(100_000)
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

        self.spy = self.add_equity("SPY", Resolution.DAILY).symbol
        sec = self.securities[self.spy]
        sec.set_fee_model(IBKRSingaporeFeeModel())
        sec.set_slippage_model(ConstantSlippageModel(0.0005))

        # 77 months in the 2020-01 to 2026-05 window
        self.monthly_budget = 100_000 / 77

        self.schedule.on(
            self.date_rules.month_start(self.spy),
            self.time_rules.at(10, 0),
            self.deposit,
        )

    def deposit(self):
        price = self.securities[self.spy].price
        if price <= 0:
            return
        cash = self.portfolio.cash
        spend = min(self.monthly_budget, cash)
        if spend <= 0:
            return
        shares = int(spend / price)
        if shares > 0:
            self.market_order(self.spy, shares)
