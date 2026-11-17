"""
PharmaTrack-X Decision Module
Reusable Python package for Expiry-Risk and Demand-Uncertainty-Aware Pharmacy Inventory Decision Support.
Implements FR-38 to FR-45, Table 3.20, and Section 5.4.
"""

from .forecaster import DemandForecaster, ForecastResult
from .engine import DecisionEngine, RecommendationResult, BatchInput, ModuleParameters

__version__ = "1.0.0"
__all__ = [
    "DemandForecaster",
    "ForecastResult",
    "DecisionEngine",
    "RecommendationResult",
    "BatchInput",
    "ModuleParameters",
]
