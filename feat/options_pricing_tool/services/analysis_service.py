from datetime import datetime
from typing import List
import logging

from ..models.option_data import (
    AnalysisRequest, AnalysisResult, PricingResult, OptionType
)
from .data_service import DataService
from .black_scholes import BlackScholesEngine
from .power_law import PowerLawEngine

logger = logging.getLogger(__name__)

class AnalysisService:
    """Main service orchestrating the options pricing analysis"""
    
    def __init__(self):
        self.data_service = DataService()
        self.black_scholes = BlackScholesEngine()
        self.power_law = PowerLawEngine()
    
    def validate_request(self, request: AnalysisRequest) -> tuple[bool, str]:
        """
        Validate analysis request
        
        Returns:
            (is_valid, error_message)
        """
        # Validate ticker
        if not request.ticker or not request.ticker.strip():
            return False, "Ticker symbol is required"
        
        ticker = request.ticker.strip().upper()
        if not self.data_service.validate_ticker(ticker):
            return False, f"Invalid ticker symbol '{ticker}' or no options data available"
        
        # Validate option type
        if request.option_type not in [OptionType.CALL, OptionType.PUT]:
            return False, "Option type must be 'call' or 'put'"
        
        # Validate date range if provided
        if request.date_range:
            start_date, end_date = request.date_range
            if start_date >= end_date:
                return False, "Start date must be before end date"
        
        # Validate alpha values
        if request.alpha_values:
            for alpha in request.alpha_values:
                if not (2.0 <= alpha <= 4.0):
                    return False, f"Alpha value {alpha} must be between 2.0 and 4.0"
        
        return True, ""
    
    def run_analysis(self, request: AnalysisRequest) -> AnalysisResult:
        """
        Run complete options pricing analysis
        
        Args:
            request: Analysis parameters
            
        Returns:
            Complete analysis results
            
        Raises:
            ValueError: If validation fails
            Exception: If analysis fails
        """
        # Validate request
        is_valid, error_msg = self.validate_request(request)
        if not is_valid:
            raise ValueError(error_msg)
        
        ticker = request.ticker.strip().upper()
        
        try:
            logger.info("="*80)
            logger.info(f"🚀 STARTING OPTIONS PRICING ANALYSIS")
            logger.info(f"   Ticker: {ticker}")
            logger.info(f"   Option Type: {request.option_type.value.upper()}")
            logger.info(f"   Date Range: {request.date_range if request.date_range else 'Default (6 months)'}")
            logger.info(f"   Strike Range: {request.strike_range if request.strike_range else 'All available'}")
            logger.info(f"   Alpha Values: {request.alpha_values}")
            if request.custom_iv is not None:
                logger.info(f"   Custom IV: {request.custom_iv:.4f} ({request.custom_iv*100:.2f}%)")
            logger.info("="*80)
            
            # Fetch all required data
            underlying, contracts, percentile_returns = self.data_service.fetch_complete_data(request)
            
            if not contracts:
                raise ValueError(f"No option contracts found for {ticker}")
            
            logger.info(f"📊 SUMMARY: Found {len(contracts)} contracts across {len(set(c.expiry for c in contracts))} expiry dates")
            logger.info(f"💰 UNDERLYING STOCK INFO:")
            logger.info(f"   Current Price: ${underlying.current_price:.2f}")
            logger.info(f"   Risk-free Rate: {underlying.risk_free_rate:.4f} ({underlying.risk_free_rate*100:.2f}%)")
            logger.info(f"   Dividend Yield: {underlying.dividend_yield:.4f} ({underlying.dividend_yield*100:.2f}%)")
            
            logger.info(f"🎯 95TH PERCENTILE RETURNS by expiry days:")
            for days, return_pct in percentile_returns.items():
                logger.info(f"   {days} days: {return_pct:.4f} ({return_pct*100:.2f}%)")
            
            # Calculate Black-Scholes prices
            logger.info("\n" + "="*60)
            logger.info("🧮 BLACK-SCHOLES PRICING ENGINE")
            logger.info("="*60)
            bs_prices = self.black_scholes.price_contracts(contracts, underlying, request.custom_iv)
            
            # Calculate Power Law prices
            logger.info("\n" + "="*60)
            logger.info("⚡ POWER LAW PRICING ENGINE")
            logger.info("="*60)
            pl_prices, pl_fallbacks = self.power_law.price_contracts(
                contracts, underlying, percentile_returns, request.alpha_values
            )
            
            # Combine results
            pricing_results = []
            for contract in contracts:
                key = (contract.strike, contract.expiry, contract.option_type)
                
                bs_price = bs_prices.get(key, 0.0)
                pl_price_dict = pl_prices.get(key, {})
                pl_fallback_used = pl_fallbacks.get(key, False)
                
                result = PricingResult(
                    strike=contract.strike,
                    expiry=contract.expiry,
                    market_price=contract.market_price,
                    black_scholes_price=bs_price,
                    power_law_prices=pl_price_dict,
                    power_law_fallback_used=pl_fallback_used
                )
                pricing_results.append(result)
            
            # Sort results by expiry then strike
            pricing_results.sort(key=lambda x: (x.expiry, x.strike))
            
            analysis_result = AnalysisResult(
                ticker=ticker,
                option_type=request.option_type,
                underlying_data=underlying,
                pricing_results=pricing_results,
                percentile_95_returns=percentile_returns,
                analysis_timestamp=datetime.now()
            )
            
            logger.info(f"Analysis completed successfully for {ticker}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Analysis failed for {ticker}: {e}")
            raise