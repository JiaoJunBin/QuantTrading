# region imports
from AlgorithmImports import *
# endregion

class ResearchHost(QCAlgorithm):
    """Placeholder algorithm.

    This QC project exists to host the research notebooks in this directory
    (01_data_exploration.ipynb, etc.). The strategies themselves live in
    sibling projects under `strategies/`.
    """

    def initialize(self):
        self.set_start_date(2024, 1, 1)
        self.set_end_date(2024, 1, 2)
        self.set_cash(100_000)
