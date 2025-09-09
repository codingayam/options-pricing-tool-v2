#!/usr/bin/env python3
"""
Run options analysis with detailed logging exported to file
"""
import logging
import sys
from datetime import datetime

# Set up detailed logging to file
log_filename = f"options_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler(sys.stdout)  # Also show on console
    ]
)

from options_pricing_tool.models.option_data import AnalysisRequest, OptionType
from options_pricing_tool.services.analysis_service import AnalysisService

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 run_with_logs.py <TICKER> <call|put> [min_strike] [max_strike]")
        print("Example: python3 run_with_logs.py SLV call 28 30")
        sys.exit(1)
    
    ticker = sys.argv[1].upper()
    option_type_str = sys.argv[2].lower()
    
    if option_type_str not in ['call', 'put']:
        print("Option type must be 'call' or 'put'")
        sys.exit(1)
    
    option_type = OptionType.CALL if option_type_str == 'call' else OptionType.PUT
    
    strike_range = None
    if len(sys.argv) >= 5:
        min_strike = float(sys.argv[3])
        max_strike = float(sys.argv[4])
        strike_range = (min_strike, max_strike)
    
    print(f"🔬 DETAILED OPTIONS ANALYSIS")
    print(f"Ticker: {ticker}")
    print(f"Option Type: {option_type_str.upper()}")
    print(f"Strike Range: {strike_range}")
    print(f"Log file: {log_filename}")
    print("="*60)
    
    try:
        # Create analysis request
        request = AnalysisRequest(
            ticker=ticker,
            option_type=option_type,
            strike_range=strike_range,
            alpha_values=[3.0]  # Single alpha for cleaner logs
        )
        
        # Run analysis with detailed logging
        analysis_service = AnalysisService()
        result = analysis_service.run_analysis(request)
        
        print(f"\n✅ Analysis complete! Check '{log_filename}' for detailed calculations")
        print(f"Found {len(result.pricing_results)} contracts")
        
        # Show summary
        print("\n📋 QUICK SUMMARY:")
        for pricing in result.pricing_results[:5]:  # Show first 5
            pl_price = pricing.power_law_prices.get(3.0, 0)
            print(f"  Strike ${pricing.strike}: Market=${pricing.market_price:.3f}, "
                  f"BS=${pricing.black_scholes_price:.3f}, PL=${pl_price:.3f}")
        
        if len(result.pricing_results) > 5:
            print(f"  ... and {len(result.pricing_results) - 5} more contracts (see log file)")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()