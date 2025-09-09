import numpy as np
from scipy.stats import norm
from datetime import date
from typing import Dict, List, Optional
import logging

from ..models.option_data import OptionContract, UnderlyingData, OptionType
from ..utils.error_handling import (
    CalculationError, validate_positive, safe_divide, safe_log, 
    log_performance, retry_on_failure
)

logger = logging.getLogger(__name__)

class BlackScholesEngine:
    """
    Black-Scholes pricing engine for options
    
    Formulas:
    Call: C = S0 * N(d1) - K * e^(-r*t) * N(d2)
    Put:  P = K * e^(-r*t) * N(-d2) - S0 * N(-d1)
    
    Where:
    d1 = (ln(S0/K) + (r + σ²/2)*t) / (σ*√t)
    d2 = d1 - σ*√t
    """
    
    def __init__(self):
        pass
    
    def _calculate_d1_d2(self, S0: float, K: float, r: float, t: float, sigma: float) -> tuple[float, float]:
        """Calculate d1 and d2 parameters for Black-Scholes"""
        validate_positive(t, "Time to expiry")
        validate_positive(sigma, "Volatility")
        validate_positive(S0, "Stock price")
        validate_positive(K, "Strike price")
            
        try:
            d1 = (safe_log(safe_divide(S0, K)) + (r + 0.5 * sigma**2) * t) / (sigma * np.sqrt(t))
            d2 = d1 - sigma * np.sqrt(t)
            
            return d1, d2
        except Exception as e:
            raise CalculationError(f"Error calculating d1, d2: {e}")
    
    def calculate_call_price(self, S0: float, K: float, r: float, t: float, sigma: float) -> float:
        """
        Calculate Black-Scholes call option price
        
        Args:
            S0: Current stock price
            K: Strike price
            r: Risk-free rate
            t: Time to expiry (in years)
            sigma: Volatility
            
        Returns:
            Call option price
        """
        try:
            d1, d2 = self._calculate_d1_d2(S0, K, r, t, sigma)
            
            # Log the detailed calculation
            logger.info(f"      🧮 BLACK-SCHOLES CALL: K={K}, S0={S0:.2f}")
            logger.info(f"         Parameters: r={r:.4f}, t={t:.4f}, σ={sigma:.4f}")
            logger.info(f"         d1={d1:.6f}, d2={d2:.6f}")
            logger.info(f"         N(d1)={norm.cdf(d1):.6f}, N(d2)={norm.cdf(d2):.6f}")
            
            term1 = S0 * norm.cdf(d1)
            term2 = K * np.exp(-r * t) * norm.cdf(d2)
            call_price = term1 - term2
            
            logger.info(f"         Formula: C = {S0:.2f}×N(d1) - {K}×e^(-{r:.4f}×{t:.4f})×N(d2)")
            logger.info(f"         C = {term1:.6f} - {term2:.6f} = {call_price:.6f}")
            
            return max(call_price, 0.0)  # Ensure non-negative price
            
        except Exception as e:
            logger.error(f"Error calculating call price: {e}")
            return 0.0
    
    def calculate_put_price(self, S0: float, K: float, r: float, t: float, sigma: float) -> float:
        """
        Calculate Black-Scholes put option price
        
        Args:
            S0: Current stock price
            K: Strike price
            r: Risk-free rate
            t: Time to expiry (in years)
            sigma: Volatility
            
        Returns:
            Put option price
        """
        try:
            d1, d2 = self._calculate_d1_d2(S0, K, r, t, sigma)
            
            # Log the detailed calculation
            logger.info(f"      🧮 BLACK-SCHOLES PUT: K={K}, S0={S0:.2f}")
            logger.info(f"         Parameters: r={r:.4f}, t={t:.4f}, σ={sigma:.4f}")
            logger.info(f"         d1={d1:.6f}, d2={d2:.6f}")
            logger.info(f"         N(-d1)={norm.cdf(-d1):.6f}, N(-d2)={norm.cdf(-d2):.6f}")
            
            term1 = K * np.exp(-r * t) * norm.cdf(-d2)
            term2 = S0 * norm.cdf(-d1)
            put_price = term1 - term2
            
            logger.info(f"         Formula: P = {K}×e^(-{r:.4f}×{t:.4f})×N(-d2) - {S0:.2f}×N(-d1)")
            logger.info(f"         P = {term1:.6f} - {term2:.6f} = {put_price:.6f}")
            
            return max(put_price, 0.0)  # Ensure non-negative price
            
        except Exception as e:
            logger.error(f"Error calculating put price: {e}")
            return 0.0
    
    def calculate_implied_volatility(self, market_price: float, S0: float, K: float, 
                                   r: float, t: float, option_type: OptionType,
                                   max_iterations: int = 100, tolerance: float = 1e-5) -> float:
        """
        Calculate implied volatility using Newton-Raphson method
        """
        if t <= 0:
            return 0.0
            
        # Initial guess
        sigma = 0.2
        
        for i in range(max_iterations):
            if option_type == OptionType.CALL:
                price = self.calculate_call_price(S0, K, r, t, sigma)
            else:
                price = self.calculate_put_price(S0, K, r, t, sigma)
            
            # Calculate vega (price sensitivity to volatility)
            d1, _ = self._calculate_d1_d2(S0, K, r, t, sigma)
            vega = S0 * norm.pdf(d1) * np.sqrt(t)
            
            if abs(vega) < 1e-10:
                break
                
            # Newton-Raphson update
            diff = price - market_price
            if abs(diff) < tolerance:
                break
                
            sigma = sigma - diff / vega
            
            # Ensure positive volatility
            sigma = max(sigma, 1e-6)
            
        return sigma
    
    @log_performance
    def price_contracts(self, contracts: List[OptionContract], 
                       underlying: UnderlyingData, custom_iv: Optional[float] = None) -> Dict[tuple, float]:
        """
        Price multiple option contracts using Black-Scholes
        
        Returns:
            Dict mapping (strike, expiry, option_type) -> price
        """
        prices = {}
        
        for contract in contracts:
            try:
                # Calculate time to expiry in years
                days_to_expiry = (contract.expiry - date.today()).days
                if days_to_expiry <= 0:
                    prices[(contract.strike, contract.expiry, contract.option_type)] = 0.0
                    continue
                    
                t = days_to_expiry / 252.0
                
                # Use custom IV if provided, otherwise use contract IV or estimate
                if custom_iv is not None:
                    sigma = custom_iv
                    logger.info(f"      Using custom IV: {sigma:.4f} ({sigma*100:.2f}%)")
                elif contract.implied_volatility and contract.implied_volatility > 0:
                    sigma = contract.implied_volatility
                    logger.info(f"      Using Yahoo Finance IV: {sigma:.4f} ({sigma*100:.2f}%)")
                else:
                    # Estimate volatility from historical prices
                    sigma = self._estimate_volatility(underlying.historical_prices)
                    logger.info(f"      Using estimated IV: {sigma:.4f} ({sigma*100:.2f}%)")
                
                # Calculate price
                if contract.option_type == OptionType.CALL:
                    price = self.calculate_call_price(
                        S0=underlying.current_price,
                        K=contract.strike,
                        r=underlying.risk_free_rate,
                        t=t,
                        sigma=sigma
                    )
                else:
                    price = self.calculate_put_price(
                        S0=underlying.current_price,
                        K=contract.strike,
                        r=underlying.risk_free_rate,
                        t=t,
                        sigma=sigma
                    )
                
                prices[(contract.strike, contract.expiry, contract.option_type)] = price
                
            except Exception as e:
                logger.warning(f"Failed to price contract {contract.strike} {contract.expiry}: {e}")
                prices[(contract.strike, contract.expiry, contract.option_type)] = 0.0
        
        return prices
    
    def _estimate_volatility(self, historical_prices: List[float], 
                           lookback_days: int = 30) -> float:
        """Estimate volatility from historical prices"""
        if len(historical_prices) < 2:
            return 0.2  # Default volatility
        
        prices = np.array(historical_prices[-lookback_days:])
        if len(prices) < 2:
            return 0.2
            
        # Calculate daily returns
        returns = np.diff(np.log(prices))
        
        # Annualize volatility (assuming 252 trading days)
        daily_vol = np.std(returns)
        annual_vol = daily_vol * np.sqrt(252)
        
        return max(annual_vol, 0.01)  # Minimum 1% volatility