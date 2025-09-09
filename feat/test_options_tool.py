#!/usr/bin/env python3
"""
Test script for Options Pricing Comparison Tool
"""
import sys
import os
import unittest
from datetime import date, timedelta
import logging

# Add the options_pricing_tool to the path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from options_pricing_tool.models.option_data import AnalysisRequest, OptionType
    from options_pricing_tool.services.analysis_service import AnalysisService
    from options_pricing_tool.services.black_scholes import BlackScholesEngine
    from options_pricing_tool.services.power_law import PowerLawEngine
    from options_pricing_tool.services.data_service import DataService
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the correct directory")
    sys.exit(1)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestOptionsToolBasic(unittest.TestCase):
    """Basic functionality tests"""
    
    def setUp(self):
        self.analysis_service = AnalysisService()
        self.data_service = DataService()
        self.bs_engine = BlackScholesEngine()
        self.pl_engine = PowerLawEngine()
    
    def test_ticker_validation(self):
        """Test ticker validation"""
        # Test valid ticker
        valid_tickers = ["AAPL", "MSFT", "TSLA", "SPY"]
        
        for ticker in valid_tickers:
            try:
                is_valid = self.data_service.validate_ticker(ticker)
                print(f"✓ {ticker}: {'Valid' if is_valid else 'Invalid'}")
            except Exception as e:
                print(f"✗ {ticker}: Error - {e}")
    
    def test_black_scholes_calculations(self):
        """Test Black-Scholes pricing calculations"""
        # Test parameters
        S0 = 100.0  # Current stock price
        K = 105.0   # Strike price
        r = 0.05    # Risk-free rate (5%)
        t = 0.25    # Time to expiry (3 months)
        sigma = 0.2 # Volatility (20%)
        
        # Test call option
        call_price = self.bs_engine.calculate_call_price(S0, K, r, t, sigma)
        self.assertGreater(call_price, 0, "Call price should be positive")
        self.assertLess(call_price, S0, "Call price should be less than stock price")
        
        # Test put option  
        put_price = self.bs_engine.calculate_put_price(S0, K, r, t, sigma)
        self.assertGreater(put_price, 0, "Put price should be positive")
        
        print(f"✓ Black-Scholes Call: ${call_price:.2f}")
        print(f"✓ Black-Scholes Put: ${put_price:.2f}")
    
    def test_power_law_calculations(self):
        """Test Power Law pricing calculations"""
        # Test parameters
        S0 = 100.0   # Current stock price
        K1 = 105.0   # Reference strike
        K2 = 110.0   # Target strike
        C_K1 = 2.50  # Reference option price
        alpha = 3.0  # Power law exponent
        
        # Test call option
        call_price = self.pl_engine.calculate_call_price(K2, S0, K1, C_K1, alpha)
        self.assertGreaterEqual(call_price, 0, "Power Law call price should be non-negative")
        
        # Test put option
        P_K1 = 5.00  # Reference put price
        put_price = self.pl_engine.calculate_put_price(K2, S0, K1, P_K1, alpha)
        self.assertGreaterEqual(put_price, 0, "Power Law put price should be non-negative")
        
        print(f"✓ Power Law Call: ${call_price:.2f}")
        print(f"✓ Power Law Put: ${put_price:.2f}")

def test_live_data_analysis():
    """Test with live market data"""
    print("\n" + "="*60)
    print("LIVE DATA ANALYSIS TEST")
    print("="*60)
    
    analysis_service = AnalysisService()
    
    # Test with AAPL (usually has good options liquidity)
    test_cases = [
        ("AAPL", OptionType.CALL),
        ("MSFT", OptionType.PUT),
    ]
    
    for ticker, option_type in test_cases:
        print(f"\nTesting {ticker} {option_type.value} options...")
        
        try:
            # Create request
            request = AnalysisRequest(
                ticker=ticker,
                option_type=option_type,
                date_range=None,  # Use default (next 6 months)
                alpha_values=[2.5, 3.0, 3.5]  # Reduced set for faster testing
            )
            
            # Run analysis
            result = analysis_service.run_analysis(request)
            
            print(f"✓ Analysis completed for {ticker}")
            print(f"  - Current stock price: ${result.underlying_data.current_price:.2f}")
            print(f"  - Risk-free rate: {result.underlying_data.risk_free_rate*100:.2f}%")
            print(f"  - Contracts found: {len(result.pricing_results)}")
            
            # Show first few results
            if result.pricing_results:
                print("  - Sample results:")
                for i, pricing in enumerate(result.pricing_results[:3]):
                    bs_price = pricing.black_scholes_price
                    pl_price = pricing.power_law_prices.get(3.0, 0)
                    market_price = pricing.market_price
                    
                    print(f"    Strike ${pricing.strike:.0f}: Market=${market_price:.2f}, "
                          f"BS=${bs_price:.2f}, PL=${pl_price:.2f}")
            
            print(f"✓ {ticker} analysis successful!")
            
        except Exception as e:
            print(f"✗ {ticker} analysis failed: {e}")
            continue

def test_edge_cases():
    """Test edge cases and error handling"""
    print("\n" + "="*60)
    print("EDGE CASES AND ERROR HANDLING TEST")
    print("="*60)
    
    analysis_service = AnalysisService()
    
    # Test invalid ticker
    print("\n1. Testing invalid ticker...")
    try:
        request = AnalysisRequest(ticker="INVALID", option_type=OptionType.CALL)
        result = analysis_service.run_analysis(request)
        print("✗ Should have failed with invalid ticker")
    except Exception as e:
        print(f"✓ Correctly rejected invalid ticker: {e}")
    
    # Test extreme alpha values
    print("\n2. Testing extreme alpha values...")
    try:
        request = AnalysisRequest(
            ticker="AAPL", 
            option_type=OptionType.CALL,
            alpha_values=[1.0, 5.0]  # Outside valid range
        )
        result = analysis_service.run_analysis(request)
        print("✗ Should have failed with invalid alpha values")
    except Exception as e:
        print(f"✓ Correctly rejected invalid alpha values: {e}")
    
    # Test invalid date range
    print("\n3. Testing invalid date range...")
    try:
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        request = AnalysisRequest(
            ticker="AAPL",
            option_type=OptionType.CALL,
            date_range=(today, yesterday)  # End before start
        )
        result = analysis_service.run_analysis(request)
        print("✗ Should have failed with invalid date range")
    except Exception as e:
        print(f"✓ Correctly rejected invalid date range: {e}")

def performance_test():
    """Test performance with multiple tickers"""
    print("\n" + "="*60)
    print("PERFORMANCE TEST")
    print("="*60)
    
    import time
    
    analysis_service = AnalysisService()
    tickers = ["SPY", "QQQ", "IWM"]  # ETFs usually have good options data
    
    total_start_time = time.time()
    
    for ticker in tickers:
        print(f"\nTesting {ticker}...")
        start_time = time.time()
        
        try:
            request = AnalysisRequest(
                ticker=ticker,
                option_type=OptionType.CALL,
                alpha_values=[3.0]  # Single alpha for speed
            )
            
            result = analysis_service.run_analysis(request)
            
            execution_time = time.time() - start_time
            print(f"✓ {ticker} completed in {execution_time:.2f}s "
                  f"({len(result.pricing_results)} contracts)")
            
        except Exception as e:
            execution_time = time.time() - start_time
            print(f"✗ {ticker} failed in {execution_time:.2f}s: {e}")
    
    total_time = time.time() - total_start_time
    print(f"\nTotal test time: {total_time:.2f}s")

def main():
    """Run all tests"""
    print("Options Pricing Comparison Tool - Test Suite")
    print("=" * 60)
    
    # Run unit tests
    print("\nRunning unit tests...")
    unittest.main(argv=[''], exit=False, verbosity=1)
    
    # Run integration tests
    test_live_data_analysis()
    test_edge_cases()
    performance_test()
    
    print("\n" + "="*60)
    print("TEST SUITE COMPLETED")
    print("="*60)
    print("\nNext steps:")
    print("1. Run the web interface: python -m options_pricing_tool.main")
    print("2. Test CLI interface: python -m options_pricing_tool.cli AAPL call")
    print("3. Access web UI at: http://localhost:8000")

if __name__ == "__main__":
    main()