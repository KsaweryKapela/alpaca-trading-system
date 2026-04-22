"""Stock selection framework — Alpha Layer.

Separates stock selection from execution strategy.
Selectors score and rank stocks; strategies trade only selected stocks.
"""

from .base import Selector, ScoredStock
from .momentum import MomentumSelector
from .composite import CompositeSelector
from .adaptive import AdaptiveSelector
from .abnormality import AbnormalitySelector

__all__ = ["Selector", "ScoredStock", "MomentumSelector", "CompositeSelector",
           "AdaptiveSelector", "AbnormalitySelector"]
