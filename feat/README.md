# Options Pricing Comparison Tool

A comprehensive tool for comparing market prices of options against Black-Scholes and Power Law pricing models. This tool helps traders and analysts identify potential mispricings and make informed trading decisions.

## Features

- **Multi-Model Pricing**: Compare market prices with Black-Scholes and Power Law models
- **Interactive Charts**: Visualize pricing differences across strike prices and expiry dates
- **Real-Time Data**: Fetch live options data using yfinance
- **Web Interface**: User-friendly web application with responsive design
- **CLI Interface**: Command-line tool for batch analysis and automation
- **Comprehensive Analysis**: Analyze multiple expiry dates and strike prices simultaneously

## Pricing Models

### Black-Scholes Model
Traditional options pricing using:
- **Call**: `C = S₀ × N(d₁) - K × e^(-r×t) × N(d₂)`
- **Put**: `P = K × e^(-r×t) × N(-d₂) - S₀ × N(-d₁)`

### Power Law Model  
Alternative pricing based on tail risk assumptions:
- **Call**: `C(K₂) = (((K₂-S₀)/(K₁-S₀))^(1-α)) × C(K₁)`
- **Put**: `P(K₂) = P(K₁) × ((K₂-S₀)^(1-α) - (S₀^(1-α) × ((α-1)×K₂ + S₀)) / ((K₁-S₀)^(1-α) - (S₀^(1-α))×((α-1)×K₁ + S₀)))`

Where α (alpha) ranges from 2.0 to 4.0 in 0.5 increments.

## Installation

### Prerequisites
- Python 3.11+
- Required packages (will be installed automatically):
  - fastapi
  - uvicorn
  - yfinance
  - numpy
  - scipy
  - pandas
  - pydantic
  - jinja2

### Quick Start

1. **Check Dependencies**:
   ```bash
   python start_options_tool.py check
   ```

2. **Install Missing Packages** (if needed):
   ```bash
   pip install fastapi uvicorn yfinance numpy scipy pandas pydantic jinja2
   ```

3. **Run Tests**:
   ```bash
   python start_options_tool.py test
   ```

4. **Start Web Interface**:
   ```bash
   python start_options_tool.py web
   ```
   Then open http://localhost:8000 in your browser

## Usage

### Web Interface

1. Navigate to http://localhost:8000
2. Enter a ticker symbol (e.g., AAPL, TSLA, SPY)
3. Select Call or Put options
4. Optionally set date range for expiry analysis
5. Click "Analyze Options" to generate comparison charts

### Command Line Interface

```bash
# Basic analysis
python -m options_pricing_tool.cli AAPL call

# With date range
python -m options_pricing_tool.cli AAPL put --start-date 2024-01-01 --end-date 2024-06-30

# Custom alpha values
python -m options_pricing_tool.cli TSLA call --alpha 2.5 3.0 3.5

# Different output formats
python -m options_pricing_tool.cli SPY call --output json
python -m options_pricing_tool.cli SPY call --output csv

# Validate ticker only
python -m options_pricing_tool.cli MSFT call --validate-only
```

### API Endpoints

The tool provides REST API endpoints:

- `GET /options/validate/{ticker}` - Validate ticker
- `POST /options/analyze` - Run complete analysis
- `GET /options/health` - Health check
- `GET /` - Web interface

## Architecture

```
options_pricing_tool/
├── models/           # Data models and structures
├── services/         # Business logic
│   ├── data_service.py      # yfinance integration
│   ├── black_scholes.py     # Black-Scholes engine
│   ├── power_law.py         # Power Law engine
│   └── analysis_service.py  # Main orchestrator
├── api/              # FastAPI endpoints
├── templates/        # HTML templates
├── utils/            # Error handling and utilities
├── main.py           # FastAPI application
└── cli.py            # Command-line interface
```

## Key Components

### Data Service
- Fetches real-time options chains using yfinance
- Validates ticker symbols and options availability
- Calculates 95th percentile returns for Power Law model
- Handles API failures with retry logic

### Black-Scholes Engine
- Implements standard Black-Scholes formulas
- Handles both call and put options
- Calculates implied volatility when needed
- Includes comprehensive error handling

### Power Law Engine
- Implements Power Law pricing formulas from requirements
- Finds reference strikes based on 95th percentile returns
- Supports multiple alpha values (2.0-4.0)
- Handles mathematical edge cases safely

### Analysis Service
- Orchestrates complete pricing analysis
- Validates inputs and handles errors
- Combines results from all pricing models
- Provides performance monitoring

## Error Handling

The tool includes comprehensive error handling:
- Input validation for all parameters
- Graceful handling of API failures
- Mathematical edge case protection
- Detailed logging and error messages
- Retry logic for transient failures

## Performance Features

- Caching of calculated values
- Parallel processing where possible
- Progress indicators for long operations
- Configurable timeouts
- Performance monitoring and logging

## Testing

Run the comprehensive test suite:

```bash
python test_options_tool.py
```

Tests include:
- Unit tests for pricing engines
- Integration tests with live data
- Edge case and error handling tests
- Performance benchmarking

## Example Output

### Web Interface
Interactive charts showing:
- Strike prices on X-axis
- Option prices on Y-axis  
- Three colored lines for Market, Black-Scholes, and Power Law prices
- Separate charts for each expiry date
- Hover tooltips with exact values

### CLI Output
```
📊 Analysis Results for AAPL CALL Options
================================================================================
Current Stock Price: $150.25
Risk-Free Rate: 4.50%
Analysis Time: 2024-09-04 14:30:15
Total Contracts: 45

📅 Expiry: 2024-10-18 (15 contracts)
--------------------------------------------------------------------------------
┌──────────┬─────────┬──────────────────┬────────────────────┬──────────────┐
│ Strike   │ Market  │ Black-Scholes    │ Power Law (α=3.0)  │ Difference   │
├──────────┼─────────┼──────────────────┼────────────────────┼──────────────┤
│ $140.00  │ $12.50  │ $13.25           │ $11.85             │ +6.0%        │
│ $145.00  │ $8.75   │ $9.10            │ $8.20              │ +4.0%        │
│ $150.00  │ $5.25   │ $5.45            │ $5.10              │ +3.8%        │
└──────────┴─────────┴──────────────────┴────────────────────┴──────────────┘
```

## Limitations

- Requires active internet connection for real-time data
- yfinance API rate limits may apply
- Options data availability varies by ticker
- Power Law model assumes specific market conditions
- Historical data used for volatility estimation

## Contributing

1. Follow existing code structure and patterns
2. Add comprehensive error handling
3. Include unit tests for new features
4. Update documentation for API changes
5. Test with multiple tickers before submitting

## License

This tool is part of the AI Hedge Fund project and follows the same licensing terms.

## Support

For issues or questions:
1. Check the test suite results
2. Verify ticker has options data available
3. Review error logs for specific issues
4. Test with known liquid options (SPY, QQQ, AAPL)