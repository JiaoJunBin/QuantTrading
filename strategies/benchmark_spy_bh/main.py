# region imports
from AlgorithmImports import *
# endregion


class IBKRSingaporeFeeModel(FeeModel):
    def get_order_fee(self, parameters):
        quantity = abs(parameters.order.absolute_quantity)
        commission = max(0.35, quantity * 0.0035) + 0.10
        return OrderFee(CashAmount(commission * 1.09, "USD"))


class BenchmarkSPYBuyHold(QCAlgorithm):
    """Lump-sum SPY buy and hold. Reference baseline for all strategies."""

    def initialize(self):
        self.set_start_date(2020, 1, 1)
        self.set_end_date(2026, 5, 15)
        self.set_cash(100_000)
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

        self.spy = self.add_equity("SPY", Resolution.DAILY).symbol
        sec = self.securities[self.spy]
        sec.set_fee_model(IBKRSingaporeFeeModel())
        sec.set_slippage_model(ConstantSlippageModel(0.0005))

    def on_data(self, slice):
        if not self.portfolio[self.spy].invested and self.spy in slice.bars:
            self.set_holdings(self.spy, 1.0)
