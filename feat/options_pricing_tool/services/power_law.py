import numpy as np
from datetime import date
from typing import Dict, List, Tuple
import logging

from ..models.option_data import OptionContract, UnderlyingData, OptionType

logger = logging.getLogger(__name__)

class PowerLawEngine:
    """
    Power Law pricing engine for options
    
    Call Formula:
    C(K2) = (((K2-S0)/(K1-S0))^(1-alpha)) * C(K1)
    
    Put Formula:
    P(K2) = P(K1) * ( (K2-S0)^(1-alpha) - ( S0^(1-alpha) * ((alpha-1)*K2 + S0)) / ( (K1-S0)^(1-alpha) - (S0^(1-alpha))*((alpha-1)*K1 + S0)))
    
    Where:
    - C(K2)/P(K2): price of call/put option at target strike K2 under power law
    - C(K1)/P(K1): price of call/put option at reference strike K1 (closest to 95th percentile return)
    - K1: strike price closest to 95th percentile return
    - K2: target strike price for calculation
    - S0: current underlying price
    - alpha: power law exponent (2.0-4.0 in 0.5 increments)
    """
    
    def __init__(self):
        self.default_alphas = [2.0, 2.5, 3.0, 3.5, 4.0]
    
    def find_reference_strike(self, contracts: List[OptionContract], 
                            underlying_price: float, percentile_return: float,
                            option_type: OptionType, expiry: date) -> Tuple[float, float]:
        """
        Find the strike price and market price closest to the 95th percentile return
        
        Args:
            contracts: Available option contracts
            underlying_price: Current stock price (S0)
            percentile_return: 95th percentile return for this expiry duration
            option_type: CALL or PUT
            expiry: Target expiry date
            
        Returns:
            (K1, C(K1)/P(K1)) - reference strike and its market price
        """
        if option_type == OptionType.CALL:
            # For calls, use upward 95th percentile return
            target_price = underlying_price * (1 + percentile_return)
        else:
            # For puts, use downward 95th percentile return
            target_price = underlying_price * (1 + percentile_return)  # percentile_return will be negative for downward moves
        
        # Find contracts for this expiry and option type
        matching_contracts = [
            c for c in contracts 
            if c.expiry == expiry and c.option_type == option_type and c.market_price > 0
        ]
        
        if not matching_contracts:
            raise ValueError(f"No contracts found for {option_type.value} options expiring on {expiry}")
        
        # Find the appropriate reference strike based on option type
        fallback_used = False
        
        if option_type == OptionType.CALL:
            # For calls, find the lowest strike price greater than target_price
            valid_contracts = [c for c in matching_contracts if c.strike > target_price]
            if not valid_contracts:
                # If no strikes above target, use the highest available strike
                valid_contracts = matching_contracts
                fallback_used = True
            best_contract = min(valid_contracts, key=lambda c: c.strike)
        else:
            # For puts, find the highest strike price less than target_price
            valid_contracts = [c for c in matching_contracts if c.strike < target_price]
            if not valid_contracts:
                # If no strikes below target, use the lowest available strike
                valid_contracts = matching_contracts
                fallback_used = True
            best_contract = max(valid_contracts, key=lambda c: c.strike)
        
        return best_contract.strike, best_contract.market_price, fallback_used
    
    def calculate_call_price(self, K2: float, S0: float, K1: float, C_K1: float, alpha: float, expiry: date = None) -> float:
        """
        Calculate Power Law call option price
        
        Formula: C(K2) = (((K2-S0)/(K1-S0))^(1-alpha)) * C(K1)
        
        Args:
            K2: Target strike price
            S0: Current underlying price
            K1: Reference strike price
            C_K1: Market price of reference call option
            alpha: Power law exponent
            
        Returns:
            Power law call option price
        """
        try:
            # Log the detailed calculation
            expiry_str = f" (exp: {expiry})" if expiry else ""
            logger.info(f"      ⚡ POWER LAW CALL{expiry_str}: K2=${K2}, K1=${K1} (ref), α={alpha}")
            logger.info(f"         Parameters: S0=${S0:.2f}, C(K1)=${C_K1:.6f}")
            
            # Handle edge cases
            if K2 == S0 or K1 == S0:
                logger.info(f"         Edge case: K2 or K1 equals S0, returning 0.0")
                return 0.0
                
            if K2 == K1:
                logger.info(f"         Edge case: K2 equals K1, returning C(K1)={C_K1}")
                return C_K1
            
            # Ensure we don't have division by zero or negative values under roots
            denominator = K1 - S0
            numerator = K2 - S0
            
            logger.info(f"         Ratio calculation: ({K2}-{S0:.2f})/({K1}-{S0:.2f}) = {numerator:.2f}/{denominator:.2f}")
            
            if abs(denominator) < 1e-10:
                logger.info(f"         Division by zero avoided, returning 0.0")
                return 0.0
            
            ratio = numerator / denominator
            logger.info(f"         Ratio = {ratio:.6f}")
            
            # Handle negative ratios (which can occur with complex strikes)
            if ratio <= 0:
                logger.info(f"         Negative ratio, returning 0.0")
                return 0.0
            
            exponent = 1 - alpha
            power_term = ratio ** exponent
            logger.info(f"         Power term: ({ratio:.6f})^({exponent:.2f}) = {power_term:.6f}")
            
            call_price = power_term * C_K1
            logger.info(f"         Formula: C(K2) = {power_term:.6f} × {C_K1:.6f} = {call_price:.6f}")
            
            return max(call_price, 0.0)  # Ensure non-negative price
            
        except Exception as e:
            logger.error(f"Error calculating power law call price: {e}")
            return 0.0
    
    def calculate_put_price(self, K2: float, S0: float, K1: float, P_K1: float, alpha: float, expiry: date = None) -> float:
        """
        Calculate Power Law put option price
        
        Formula: P(K2) = P(K1) * ( (K2-S0)^(1-alpha) - ( S0^(1-alpha) * ((alpha-1)*K2 + S0)) / ( (K1-S0)^(1-alpha) - (S0^(1-alpha))*((alpha-1)*K1 + S0)))
        
        Args:
            K2: Target strike price
            S0: Current underlying price
            K1: Reference strike price
            P_K1: Market price of reference put option
            alpha: Power law exponent
            
        Returns:
            Power law put option price
        """
        try:
            # Log the detailed calculation
            expiry_str = f" (exp: {expiry})" if expiry else ""
            logger.info(f"      ⚡ POWER LAW PUT{expiry_str}: K2=${K2}, K1=${K1} (ref), α={alpha}")
            logger.info(f"         Parameters: S0=${S0:.2f}, P(K1)=${P_K1:.6f}")
            
            # Handle edge cases
            if K2 == K1:
                logger.info(f"         Edge case: K2 equals K1, returning P(K1)={P_K1}")
                return P_K1
                
            if S0 <= 0:
                logger.info(f"         Edge case: S0 <= 0, returning 0.0")
                return 0.0
            
            # Calculate components of the formula
            exponent = 1 - alpha
            
            # Numerator: (K2-S0)^(1-alpha) - ( S0^(1-alpha) * ((alpha-1)*K2 + S0))
            term1 = (K2 - S0) ** exponent if (K2 - S0) != 0 else 0
            s0_power = S0 ** exponent
            term2 = s0_power * ((alpha - 1) * K2 + S0)
            numerator = term1 - term2
            
            # Denominator: (K1-S0)^(1-alpha) - (S0^(1-alpha))*((alpha-1)*K1 + S0)
            term3 = (K1 - S0) ** exponent if (K1 - S0) != 0 else 0
            term4 = s0_power * ((alpha - 1) * K1 + S0)
            denominator = term3 - term4
            
            if abs(denominator) < 1e-10:
                return 0.0
            
            ratio = numerator / denominator
            put_price = P_K1 * ratio
            
            return max(put_price, 0.0)  # Ensure non-negative price
            
        except Exception as e:
            logger.error(f"Error calculating power law put price: {e}")
            return 0.0
    
    def price_contracts(self, contracts: List[OptionContract], underlying: UnderlyingData,
                       percentile_returns: Dict[int, float], 
                       alpha_values: List[float] = None) -> tuple[Dict[tuple, Dict[float, float]], Dict[tuple, bool]]:
        """
        Price multiple option contracts using Power Law model
        
        Args:
            contracts: List of option contracts
            underlying: Underlying stock data
            percentile_returns: Map of expiry_days -> 95th percentile return
            alpha_values: List of alpha values to calculate
            
        Returns:
            Tuple of (prices_dict, fallback_dict) where:
            - prices_dict: Dict mapping (strike, expiry, option_type) -> {alpha: price}
            - fallback_dict: Dict mapping (strike, expiry, option_type) -> bool (fallback used)
        """
        if alpha_values is None:
            alpha_values = self.default_alphas
            
        prices = {}
        fallbacks = {}
        
        # Group contracts by expiry and option type
        contract_groups = {}
        for contract in contracts:
            key = (contract.expiry, contract.option_type)
            if key not in contract_groups:
                contract_groups[key] = []
            contract_groups[key].append(contract)
        
        # Price each group
        for (expiry, option_type), group_contracts in contract_groups.items():
            try:
                # Get days to expiry
                days_to_expiry = (expiry - date.today()).days
                
                # Log expiry group header
                logger.info(f"🗓️  PROCESSING EXPIRY: {expiry} ({days_to_expiry} days) - {option_type.value.upper()} OPTIONS")
                if days_to_expiry <= 0:
                    # Expired options have zero value
                    for contract in group_contracts:
                        prices[(contract.strike, contract.expiry, contract.option_type)] = {
                            alpha: 0.0 for alpha in alpha_values
                        }
                        fallbacks[(contract.strike, contract.expiry, contract.option_type)] = False
                    continue
                
                # Get percentile return for this expiry
                percentile_return = percentile_returns.get(days_to_expiry, 0.0)
                
                # Find reference strike and price
                try:
                    K1, ref_price, fallback_used = self.find_reference_strike(
                        group_contracts, underlying.current_price, 
                        percentile_return, option_type, expiry
                    )
                    # Log the reference strike information
                    target_price = underlying.current_price * (1 + percentile_return)
                    logger.info(f"   📌 REFERENCE STRIKE: K1=${K1:.2f}, Market Price=${ref_price:.6f}")
                    logger.info(f"      95th percentile target: ${target_price:.2f} ({percentile_return*100:+.2f}%)")
                    
                    # Log warning if fallback was used
                    if fallback_used:
                        if option_type == OptionType.CALL:
                            logger.warning(f"   ⚠️  FALLBACK USED: No strikes available above 95th percentile target ${target_price:.2f}")
                            logger.warning(f"      Using highest available strike ${K1:.2f} - Power Law accuracy may be reduced")
                        else:
                            logger.warning(f"   ⚠️  FALLBACK USED: No strikes available below 95th percentile target ${target_price:.2f}")
                            logger.warning(f"      Using lowest available strike ${K1:.2f} - Power Law accuracy may be reduced")
                except ValueError as e:
                    logger.warning(f"Could not find reference strike: {e}")
                    # Set all prices to zero if we can't find a reference
                    for contract in group_contracts:
                        prices[(contract.strike, contract.expiry, contract.option_type)] = {
                            alpha: 0.0 for alpha in alpha_values
                        }
                        fallbacks[(contract.strike, contract.expiry, contract.option_type)] = False
                    continue
                
                # Calculate prices for each contract in this group
                for contract in group_contracts:
                    K2 = contract.strike
                    S0 = underlying.current_price
                    
                    contract_prices = {}
                    for alpha in alpha_values:
                        if option_type == OptionType.CALL:
                            price = self.calculate_call_price(K2, S0, K1, ref_price, alpha, expiry)
                        else:
                            price = self.calculate_put_price(K2, S0, K1, ref_price, alpha, expiry)
                        
                        contract_prices[alpha] = price
                    
                    prices[(contract.strike, contract.expiry, contract.option_type)] = contract_prices
                    fallbacks[(contract.strike, contract.expiry, contract.option_type)] = fallback_used
                    
            except Exception as e:
                logger.error(f"Error pricing contracts for {expiry}, {option_type}: {e}")
                # Set prices to zero on error
                for contract in group_contracts:
                    prices[(contract.strike, contract.expiry, contract.option_type)] = {
                        alpha: 0.0 for alpha in alpha_values
                    }
                    fallbacks[(contract.strike, contract.expiry, contract.option_type)] = False
        
        return prices, fallbacks
    
    def get_default_alpha_display(self) -> float:
        """Get the default alpha value to display (3.0 as specified in requirements)"""
        return 3.0