from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from enum import Enum

class OptionType(Enum):
    CALL = "call"
    PUT = "put"

@dataclass
class OptionContract:
    strike: float
    expiry: date
    option_type: OptionType
    market_price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None
    implied_volatility: Optional[float] = None

@dataclass
class UnderlyingData:
    symbol: str
    current_price: float
    historical_prices: List[float]
    risk_free_rate: float
    dividend_yield: float = 0.0

@dataclass
class PricingResult:
    strike: float
    expiry: date
    market_price: float
    black_scholes_price: float
    power_law_prices: Dict[float, float]  # alpha -> price mapping
    power_law_fallback_used: bool = False  # True if reference strike fallback was used
    
@dataclass
class AnalysisRequest:
    ticker: str
    option_type: OptionType
    date_range: Optional[tuple[date, date]] = None
    strike_range: Optional[tuple[float, float]] = None
    alpha_values: List[float] = None
    custom_iv: Optional[float] = None  # User-provided implied volatility
    
    def __post_init__(self):
        if self.alpha_values is None:
            self.alpha_values = [2.0, 2.5, 3.0, 3.5, 4.0]

@dataclass
class AnalysisResult:
    ticker: str
    option_type: OptionType
    underlying_data: UnderlyingData
    pricing_results: List[PricingResult]
    percentile_95_returns: Dict[int, float]  # expiry days -> return
    analysis_timestamp: datetime