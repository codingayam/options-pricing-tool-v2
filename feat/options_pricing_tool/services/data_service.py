import yfinance as yf
import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Tuple
import logging

from ..models.option_data import (
    OptionContract, UnderlyingData, OptionType, 
    AnalysisRequest, AnalysisResult
)

logger = logging.getLogger(__name__)

class DataService:
    def __init__(self):
        self.cache = {}
        
    def validate_ticker(self, ticker: str) -> bool:
        """Validate if ticker exists and has options data"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            if not info or 'symbol' not in info:
                return False
            
            # Check if options are available
            try:
                expiry_dates = stock.options
                return len(expiry_dates) > 0
            except:
                return False
        except Exception as e:
            logger.error(f"Error validating ticker {ticker}: {e}")
            return False
    
    def get_risk_free_rate(self) -> float:
        """Get current risk-free rate from Treasury bills"""
        try:
            tnx = yf.Ticker("^TNX")
            hist = tnx.history(period="5d")
            if not hist.empty:
                return hist['Close'].iloc[-1] / 100.0
        except:
            pass
        return 0.02  # Fallback to 2%
    
    def get_max_lookback_days(self, ticker: str) -> int:
        """Determine maximum available historical data for ticker"""
        stock = yf.Ticker(ticker)
        
        # Try fetching maximum available data using period="max"
        try:
            logger.info(f"  • Detecting maximum available data for {ticker}")
            hist_max = stock.history(period="max")
            if not hist_max.empty:
                max_days = len(hist_max)
                earliest_date = hist_max.index[0].date()
                logger.info(f"  • Maximum available data: {max_days} days (from {earliest_date})")
                return max_days
        except Exception as e:
            logger.warning(f"  • Could not determine max lookback: {e}")
        
        # Fallback to default
        logger.info(f"  • Using default lookback period: 1095 days")
        return 1095

    def get_underlying_data(self, ticker: str, lookback_days: int = None) -> UnderlyingData:
        """Fetch underlying stock data"""
        stock = yf.Ticker(ticker)
        
        # Get current price
        logger.info(f"📊 YFINANCE DATA EXTRACTION for {ticker}")
        info = stock.info
        logger.info(f"  • Stock info keys available: {list(info.keys())[:10]}...")
        
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        logger.info(f"  • Current price from info: {current_price}")
        
        if not current_price:
            hist = stock.history(period="1d")
            current_price = hist['Close'].iloc[-1]
            logger.info(f"  • Current price from 1d history: {current_price}")
        
        # Determine lookback period - use max available if not specified
        if lookback_days is None:
            lookback_days = self.get_max_lookback_days(ticker)
        
        # Get historical prices
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)
        logger.info(f"  • Fetching historical data: {start_date.date()} to {end_date.date()}")
        hist = stock.history(start=start_date, end=end_date)
        historical_prices = hist['Close'].tolist()
        logger.info(f"  • Historical prices: {len(historical_prices)} days, latest={historical_prices[-1]:.2f}")
        
        # Get dividend yield
        dividend_yield = info.get('dividendYield', 0.0) or 0.0
        logger.info(f"  • Dividend yield: {dividend_yield}")
        
        risk_free_rate = self.get_risk_free_rate()
        logger.info(f"  • Risk-free rate: {risk_free_rate:.4f} ({risk_free_rate*100:.2f}%)")
        
        return UnderlyingData(
            symbol=ticker,
            current_price=float(current_price),
            historical_prices=historical_prices,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield
        )
    
    def get_options_chain(self, ticker: str, option_type: OptionType, 
                         date_range: Optional[Tuple[date, date]] = None,
                         strike_range: Optional[Tuple[float, float]] = None) -> List[OptionContract]:
        """Fetch options chain data"""
        stock = yf.Ticker(ticker)
        expiry_dates = stock.options
        
        if not expiry_dates:
            raise ValueError(f"No options available for {ticker}")
        
        # Filter expiry dates based on date range
        filtered_expiry_dates = []
        for expiry_str in expiry_dates:
            expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
            
            if date_range:
                start_date, end_date = date_range
                if start_date <= expiry_date <= end_date:
                    filtered_expiry_dates.append(expiry_str)
            else:
                # Default: next 6 months
                if expiry_date <= (datetime.now().date() + timedelta(days=180)):
                    filtered_expiry_dates.append(expiry_str)
        
        contracts = []
        logger.info(f"🔗 OPTIONS CHAIN EXTRACTION")
        for expiry_str in filtered_expiry_dates:  # Process all filtered expiry dates
            try:
                chain = stock.option_chain(expiry_str)
                expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
                
                if option_type == OptionType.CALL:
                    options_df = chain.calls
                else:
                    options_df = chain.puts
                
                logger.info(f"  📅 Expiry {expiry_str}: {len(options_df)} {option_type.value} contracts found")
                
                # Log first few contracts as examples
                if len(options_df) > 0:
                    logger.info(f"     📋 Sample raw data (first 3 contracts):")
                    for i, (_, row) in enumerate(options_df.head(3).iterrows()):
                        logger.info(f"        Contract {i+1}: Strike={row['strike']}, LastPrice={row['lastPrice']}, "
                                  f"Bid={row['bid']}, Ask={row['ask']}, Volume={row['volume']}, "
                                  f"OpenInt={row['openInterest']}, IV={row['impliedVolatility']}")
                
                for _, row in options_df.iterrows():
                    strike_price = float(row['strike'])
                    
                    # Apply strike price filtering if specified
                    if strike_range:
                        min_strike, max_strike = strike_range
                        if not (min_strike <= strike_price <= max_strike):
                            continue
                    
                    # Handle NaN values gracefully without filtering out contracts
                    # Note: implied_volatility from Yahoo Finance will be ignored if custom_iv is provided
                    contract = OptionContract(
                        strike=strike_price,
                        expiry=expiry_date,
                        option_type=option_type,
                        market_price=float(row['lastPrice']) if pd.notna(row['lastPrice']) else 0.0,
                        bid=float(row['bid']) if pd.notna(row['bid']) else None,
                        ask=float(row['ask']) if pd.notna(row['ask']) else None,
                        volume=int(row['volume']) if pd.notna(row['volume']) else None,
                        open_interest=int(row['openInterest']) if pd.notna(row['openInterest']) else None,
                        implied_volatility=float(row['impliedVolatility']) if pd.notna(row['impliedVolatility']) else None
                    )
                    contracts.append(contract)
                    
            except Exception as e:
                logger.warning(f"Error fetching options for {expiry_str}: {e}")
                continue
        
        return contracts
    
    def calculate_percentile_returns(self, historical_prices: List[float], 
                                   expiry_days: int) -> float:
        """Calculate 95th percentile return for given duration"""
        if len(historical_prices) < expiry_days:
            expiry_days = len(historical_prices) - 1
            
        prices = np.array(historical_prices)
        returns = []
        
        for i in range(len(prices) - expiry_days):
            start_price = prices[i]
            end_price = prices[i + expiry_days]
            return_pct = (end_price - start_price) / start_price
            returns.append(return_pct)
        
        if not returns:
            return 0.0
            
        return float(np.percentile(returns, 95))
    
    def fetch_complete_data(self, request: AnalysisRequest) -> Tuple[UnderlyingData, List[OptionContract], Dict[int, float]]:
        """Fetch all required data for analysis"""
        # Get underlying data
        underlying = self.get_underlying_data(request.ticker)
        
        # Get options contracts
        contracts = self.get_options_chain(request.ticker, request.option_type, request.date_range, request.strike_range)
        
        # Calculate 95th percentile returns for each expiry duration
        percentile_returns = {}
        unique_expiry_days = set()
        
        for contract in contracts:
            days_to_expiry = (contract.expiry - date.today()).days
            if days_to_expiry > 0:
                unique_expiry_days.add(days_to_expiry)
        
        for days in unique_expiry_days:
            percentile_returns[days] = self.calculate_percentile_returns(
                underlying.historical_prices, days
            )
        
        return underlying, contracts, percentile_returns