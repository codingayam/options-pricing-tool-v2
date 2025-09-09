from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date
from enum import Enum

from ..models.option_data import OptionType, AnalysisRequest
from ..services.analysis_service import AnalysisService

router = APIRouter(prefix="/options", tags=["options"])
analysis_service = AnalysisService()

class OptionTypeEnum(str, Enum):
    call = "call"
    put = "put"

class AnalysisRequestModel(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")
    option_type: OptionTypeEnum = Field(..., description="Option type: call or put")
    start_date: Optional[date] = Field(None, description="Start date for expiry range (optional)")
    end_date: Optional[date] = Field(None, description="End date for expiry range (optional)")
    min_strike: Optional[float] = Field(None, description="Minimum strike price (optional)")
    max_strike: Optional[float] = Field(None, description="Maximum strike price (optional)")
    alpha_values: Optional[List[float]] = Field(None, description="Alpha values for power law (2.0-4.0)")
    implied_volatility: Optional[float] = Field(None, ge=0.1, le=200.0, description="Custom implied volatility as percentage (0.1-200%)")

class ValidationResponse(BaseModel):
    valid: bool
    message: str = ""

class PricingResultResponse(BaseModel):
    strike: float
    expiry: date
    market_price: float
    black_scholes_price: float
    power_law_prices: dict  # alpha -> price mapping
    power_law_fallback_used: bool = False  # True if reference strike fallback was used

class AnalysisResponse(BaseModel):
    ticker: str
    option_type: str
    underlying_price: float
    risk_free_rate: float
    pricing_results: List[PricingResultResponse]
    percentile_95_returns: dict
    analysis_timestamp: str

@router.get("/validate/{ticker}")
async def validate_ticker(ticker: str) -> ValidationResponse:
    """Validate if ticker has options data available"""
    try:
        from ..services.data_service import DataService
        data_service = DataService()
        
        is_valid = data_service.validate_ticker(ticker.upper())
        
        if is_valid:
            return ValidationResponse(valid=True, message="Ticker is valid")
        else:
            return ValidationResponse(valid=False, message="Ticker not found or no options available")
            
    except Exception as e:
        return ValidationResponse(valid=False, message=f"Validation error: {str(e)}")

@router.post("/analyze")
async def analyze_options(request: AnalysisRequestModel) -> AnalysisResponse:
    """Run complete options pricing analysis"""
    try:
        # Convert request model to internal request
        date_range = None
        if request.start_date and request.end_date:
            date_range = (request.start_date, request.end_date)
            
        strike_range = None
        if request.min_strike is not None or request.max_strike is not None:
            min_strike = request.min_strike if request.min_strike is not None else 0.0
            max_strike = request.max_strike if request.max_strike is not None else float('inf')
            strike_range = (min_strike, max_strike)
        
        option_type = OptionType.CALL if request.option_type == OptionTypeEnum.call else OptionType.PUT
        
        # Convert percentage to decimal if provided
        custom_iv = None
        if request.implied_volatility is not None:
            custom_iv = request.implied_volatility / 100.0
        
        analysis_request = AnalysisRequest(
            ticker=request.ticker,
            option_type=option_type,
            date_range=date_range,
            strike_range=strike_range,
            alpha_values=request.alpha_values,
            custom_iv=custom_iv
        )
        
        # Run analysis
        result = analysis_service.run_analysis(analysis_request)
        
        # Convert to response model
        pricing_results = [
            PricingResultResponse(
                strike=pr.strike,
                expiry=pr.expiry,
                market_price=pr.market_price,
                black_scholes_price=pr.black_scholes_price,
                power_law_prices=pr.power_law_prices,
                power_law_fallback_used=pr.power_law_fallback_used
            )
            for pr in result.pricing_results
        ]
        
        return AnalysisResponse(
            ticker=result.ticker,
            option_type=result.option_type.value,
            underlying_price=result.underlying_data.current_price,
            risk_free_rate=result.underlying_data.risk_free_rate,
            pricing_results=pricing_results,
            percentile_95_returns=result.percentile_95_returns,
            analysis_timestamp=result.analysis_timestamp.isoformat()
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@router.get("/")
async def get_analysis_form():
    """Serve the options analysis form"""
    return {
        "message": "Options Pricing Comparison Tool",
        "endpoints": {
            "validate": "/options/validate/{ticker}",
            "analyze": "/options/analyze",
            "form": "/options/form"
        }
    }

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "options_pricing_tool"}