#!/usr/bin/env python3
"""
CLI interface for Options Pricing Comparison Tool
"""
import argparse
from datetime import datetime, date, timedelta
from typing import Optional
import sys
import json

from .models.option_data import AnalysisRequest, OptionType
from .services.analysis_service import AnalysisService

def main():
    parser = argparse.ArgumentParser(
        description="Options Pricing Comparison Tool - Compare Market, Black-Scholes, and Power Law pricing"
    )
    
    parser.add_argument(
        "ticker", 
        help="Stock ticker symbol (e.g., AAPL, TSLA)"
    )
    
    parser.add_argument(
        "option_type", 
        choices=["call", "put"],
        help="Option type: call or put"
    )
    
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date for expiry range (YYYY-MM-DD). Default: today"
    )
    
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date for expiry range (YYYY-MM-DD). Default: 6 months from today"
    )
    
    parser.add_argument(
        "--alpha",
        type=float,
        nargs="+",
        default=[2.0, 2.5, 3.0, 3.5, 4.0],
        help="Alpha values for Power Law model (default: 2.0 2.5 3.0 3.5 4.0)"
    )
    
    parser.add_argument(
        "--min-strike",
        type=float,
        help="Minimum strike price to analyze"
    )
    
    parser.add_argument(
        "--max-strike", 
        type=float,
        help="Maximum strike price to analyze"
    )
    
    parser.add_argument(
        "--output",
        choices=["table", "json", "csv"],
        default="table",
        help="Output format (default: table)"
    )
    
    parser.add_argument(
        "--implied-volatility",
        type=float,
        help="Custom implied volatility to use instead of Yahoo Finance IV (as percentage, e.g., 25 for 25%%)"
    )
    
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate ticker and exit"
    )
    
    args = parser.parse_args()
    
    # Validate alpha values
    for alpha in args.alpha:
        if not (2.0 <= alpha <= 4.0):
            print(f"Error: Alpha value {alpha} must be between 2.0 and 4.0")
            sys.exit(1)
    
    # Validate and convert implied volatility from percentage to decimal
    custom_iv = None
    if args.implied_volatility is not None:
        if not (0.1 <= args.implied_volatility <= 200.0):
            print(f"Error: Implied volatility {args.implied_volatility}% must be between 0.1% and 200%")
            sys.exit(1)
        custom_iv = args.implied_volatility / 100.0  # Convert percentage to decimal
    
    # Create analysis service
    analysis_service = AnalysisService()
    
    # Validate ticker
    print(f"Validating ticker {args.ticker.upper()}...")
    is_valid, error_msg = analysis_service.validate_request(
        AnalysisRequest(
            ticker=args.ticker,
            option_type=OptionType.CALL if args.option_type == "call" else OptionType.PUT
        )
    )
    
    if not is_valid:
        print(f"Error: {error_msg}")
        sys.exit(1)
    
    print(f"✓ Ticker {args.ticker.upper()} is valid")
    
    if args.validate_only:
        sys.exit(0)
    
    # Parse dates
    start_date = None
    end_date = None
    
    if args.start_date:
        try:
            start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
        except ValueError:
            print("Error: start-date must be in format YYYY-MM-DD")
            sys.exit(1)
    
    if args.end_date:
        try:
            end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()
        except ValueError:
            print("Error: end-date must be in format YYYY-MM-DD")
            sys.exit(1)
    
    date_range = None
    if start_date and end_date:
        if start_date >= end_date:
            print("Error: start-date must be before end-date")
            sys.exit(1)
        date_range = (start_date, end_date)
    
    # Parse strike range
    strike_range = None
    if args.min_strike is not None and args.max_strike is not None:
        if args.min_strike >= args.max_strike:
            print("Error: min-strike must be less than max-strike")
            sys.exit(1)
        strike_range = (args.min_strike, args.max_strike)
    elif args.min_strike is not None or args.max_strike is not None:
        print("Error: Both min-strike and max-strike must be specified together")
        sys.exit(1)
    
    # Create analysis request
    request = AnalysisRequest(
        ticker=args.ticker,
        option_type=OptionType.CALL if args.option_type == "call" else OptionType.PUT,
        date_range=date_range,
        strike_range=strike_range,
        alpha_values=args.alpha,
        custom_iv=custom_iv
    )
    
    # Run analysis
    print(f"Running analysis for {args.ticker.upper()} {args.option_type} options...")
    
    try:
        result = analysis_service.run_analysis(request)
        
        # Output results
        if args.output == "json":
            output_json(result)
        elif args.output == "csv":
            output_csv(result)
        else:
            output_table(result)
            
    except Exception as e:
        print(f"Error: Analysis failed - {e}")
        sys.exit(1)

def output_table(result):
    """Output results as formatted table"""
    from tabulate import tabulate
    
    print(f"\n📊 Analysis Results for {result.ticker} {result.option_type.value.upper()} Options")
    print("=" * 80)
    print(f"Current Stock Price: ${result.underlying_data.current_price:.2f}")
    print(f"Risk-Free Rate: {result.underlying_data.risk_free_rate*100:.2f}%")
    print(f"Analysis Time: {result.analysis_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total Contracts: {len(result.pricing_results)}")
    
    # Group by expiry
    expiry_groups = {}
    for pricing in result.pricing_results:
        expiry = pricing.expiry
        if expiry not in expiry_groups:
            expiry_groups[expiry] = []
        expiry_groups[expiry].append(pricing)
    
    for expiry in sorted(expiry_groups.keys()):
        contracts = expiry_groups[expiry]
        print(f"\n📅 Expiry: {expiry} ({len(contracts)} contracts)")
        print("-" * 80)
        
        headers = ["Strike", "Market", "Black-Scholes", "Power Law (α=3.0)", "Difference (%)"]
        rows = []
        
        for contract in sorted(contracts, key=lambda x: x.strike):
            pl_price = contract.power_law_prices.get(3.0, 0.0)
            
            # Calculate percentage difference between market and Black-Scholes
            diff_pct = 0.0
            if contract.market_price > 0:
                diff_pct = ((contract.black_scholes_price - contract.market_price) / contract.market_price) * 100
            
            rows.append([
                f"${contract.strike:.2f}",
                f"${contract.market_price:.2f}",
                f"${contract.black_scholes_price:.2f}",
                f"${pl_price:.2f}",
                f"{diff_pct:+.1f}%"
            ])
        
        print(tabulate(rows, headers=headers, tablefmt="grid"))

def output_json(result):
    """Output results as JSON"""
    # Convert result to JSON-serializable format
    data = {
        "ticker": result.ticker,
        "option_type": result.option_type.value,
        "underlying_price": result.underlying_data.current_price,
        "risk_free_rate": result.underlying_data.risk_free_rate,
        "analysis_timestamp": result.analysis_timestamp.isoformat(),
        "pricing_results": [
            {
                "strike": p.strike,
                "expiry": p.expiry.isoformat(),
                "market_price": p.market_price,
                "black_scholes_price": p.black_scholes_price,
                "power_law_prices": p.power_law_prices
            }
            for p in result.pricing_results
        ],
        "percentile_95_returns": result.percentile_95_returns
    }
    
    print(json.dumps(data, indent=2))

def output_csv(result):
    """Output results as CSV"""
    print("ticker,option_type,expiry,strike,market_price,black_scholes_price,power_law_3_0,underlying_price,risk_free_rate")
    
    for pricing in result.pricing_results:
        pl_price = pricing.power_law_prices.get(3.0, 0.0)
        print(f"{result.ticker},{result.option_type.value},{pricing.expiry},{pricing.strike},"
              f"{pricing.market_price},{pricing.black_scholes_price},{pl_price},"
              f"{result.underlying_data.current_price},{result.underlying_data.risk_free_rate}")

if __name__ == "__main__":
    main()