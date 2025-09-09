import datetime
import os
import pandas as pd
import requests
import time
import yfinance as yf
from typing import Optional, List, Dict, Any, Union

from src.data.cache import get_cache
from src.data.models import (
    CompanyNews,
    CompanyNewsResponse,
    FinancialMetrics,
    FinancialMetricsResponse,
    Price,
    PriceResponse,
    LineItem,
    LineItemResponse,
    InsiderTrade,
    InsiderTradeResponse,
    CompanyFactsResponse,
)

# Global cache instance
_cache = get_cache()


def _make_api_request(url: str, headers: dict, method: str = "GET", json_data: dict = None, max_retries: int = 3) -> requests.Response:
    """
    Make an API request with rate limiting handling and moderate backoff.
    
    Args:
        url: The URL to request
        headers: Headers to include in the request
        method: HTTP method (GET or POST)
        json_data: JSON data for POST requests
        max_retries: Maximum number of retries (default: 3)
    
    Returns:
        requests.Response: The response object
    
    Raises:
        Exception: If the request fails with a non-429 error
    """
    for attempt in range(max_retries + 1):  # +1 for initial attempt
        if method.upper() == "POST":
            response = requests.post(url, headers=headers, json=json_data)
        else:
            response = requests.get(url, headers=headers)
        
        if response.status_code == 429 and attempt < max_retries:
            # Linear backoff: 60s, 90s, 120s, 150s...
            delay = 60 + (30 * attempt)
            print(f"Rate limited (429). Attempt {attempt + 1}/{max_retries + 1}. Waiting {delay}s before retrying...")
            time.sleep(delay)
            continue
        
        # Return the response (whether success, other errors, or final 429)
        return response


def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> List[Price]:
    """Fetch price data from cache or yfinance."""
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date}_{end_date}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_prices(cache_key):
        return [Price(**price) for price in cached_data]

    # Fetch from yfinance
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(start=start_date, end=end_date)
        
        if hist.empty:
            return []
        
        # Convert to Price objects
        prices = []
        for date, row in hist.iterrows():
            price = Price(
                open=float(row['Open']),
                close=float(row['Close']),
                high=float(row['High']),
                low=float(row['Low']),
                volume=int(row['Volume']),
                time=date.strftime('%Y-%m-%d')
            )
            prices.append(price)
        
        # Cache the results using the comprehensive cache key
        _cache.set_prices(cache_key, [p.model_dump() for p in prices])
        return prices
        
    except Exception as e:
        raise Exception(f"Error fetching data from yfinance: {ticker} - {str(e)}")


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> List[FinancialMetrics]:
    """Fetch financial metrics from cache or yfinance."""
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{period}_{end_date}_{limit}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_financial_metrics(cache_key):
        return [FinancialMetrics(**metric) for metric in cached_data]

    # Fetch from yfinance
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        financials = stock.financials
        balance_sheet = stock.balance_sheet
        cashflow = stock.cashflow
        
        # Calculate financial metrics from yfinance data
        metrics = FinancialMetrics(
            ticker=ticker,
            report_period=end_date,
            period=period,
            currency=info.get('currency', 'USD'),
            market_cap=info.get('marketCap'),
            enterprise_value=info.get('enterpriseValue'),
            price_to_earnings_ratio=info.get('trailingPE'),
            price_to_book_ratio=info.get('priceToBook'),
            price_to_sales_ratio=info.get('priceToSalesTrailing12Months'),
            enterprise_value_to_ebitda_ratio=info.get('enterpriseToEbitda'),
            enterprise_value_to_revenue_ratio=info.get('enterpriseToRevenue'),
            free_cash_flow_yield=None,  # Calculate if needed
            peg_ratio=info.get('pegRatio'),
            gross_margin=info.get('grossMargins'),
            operating_margin=info.get('operatingMargins'),
            net_margin=info.get('profitMargins'),
            return_on_equity=info.get('returnOnEquity'),
            return_on_assets=info.get('returnOnAssets'),
            return_on_invested_capital=None,  # Calculate if needed
            asset_turnover=None,  # Calculate if needed
            inventory_turnover=None,  # Calculate if needed
            receivables_turnover=None,  # Calculate if needed
            days_sales_outstanding=None,  # Calculate if needed
            operating_cycle=None,  # Calculate if needed
            working_capital_turnover=None,  # Calculate if needed
            current_ratio=info.get('currentRatio'),
            quick_ratio=info.get('quickRatio'),
            cash_ratio=None,  # Calculate if needed
            operating_cash_flow_ratio=None,  # Calculate if needed
            debt_to_equity=info.get('debtToEquity'),
            debt_to_assets=None,  # Calculate if needed
            interest_coverage=None,  # Calculate if needed
            revenue_growth=info.get('revenueGrowth'),
            earnings_growth=info.get('earningsGrowth'),
            book_value_growth=None,  # Calculate if needed
            earnings_per_share_growth=None,  # Calculate if needed
            free_cash_flow_growth=None,  # Calculate if needed
            operating_income_growth=None,  # Calculate if needed
            ebitda_growth=None,  # Calculate if needed
            payout_ratio=info.get('payoutRatio'),
            earnings_per_share=info.get('trailingEps'),
            book_value_per_share=info.get('bookValue'),
            free_cash_flow_per_share=None,  # Calculate if needed
        )
        
        financial_metrics = [metrics]
        
        # Cache the results using the comprehensive cache key
        _cache.set_financial_metrics(cache_key, [m.model_dump() for m in financial_metrics])
        return financial_metrics
        
    except Exception as e:
        raise Exception(f"Error fetching financial metrics from yfinance: {ticker} - {str(e)}")


def search_line_items(
    ticker: str,
    line_items: List[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> List[LineItem]:
    """Fetch line items using yfinance as fallback."""
    # Create a cache key that includes all parameters
    cache_key = f"{ticker}_{'_'.join(sorted(line_items))}_{end_date}_{period}_{limit}"
    
    # Check cache first
    if cached_data := _cache.get_line_items(cache_key):
        return [LineItem(**item) for item in cached_data]

    # Fetch from yfinance
    try:
        stock = yf.Ticker(ticker)
        
        # Get financial statements
        financials = stock.financials  # Income statement (annual)
        quarterly_financials = stock.quarterly_financials  # Income statement (quarterly)
        balance_sheet = stock.balance_sheet  # Balance sheet (annual)
        quarterly_balance_sheet = stock.quarterly_balance_sheet  # Balance sheet (quarterly)
        cashflow = stock.cashflow  # Cash flow (annual)
        quarterly_cashflow = stock.quarterly_cashflow  # Cash flow (quarterly)
        
        # Use quarterly data for TTM calculations
        data_sources = {
            'financials': quarterly_financials if period == 'ttm' else financials,
            'balance_sheet': quarterly_balance_sheet if period == 'ttm' else balance_sheet,
            'cashflow': quarterly_cashflow if period == 'ttm' else cashflow
        }
        
        results = []
        
        # Get the most recent periods (limit determines how many periods)
        for i in range(min(limit, len(data_sources['financials'].columns) if not data_sources['financials'].empty else 0)):
            line_item_values = {}
            date_col = data_sources['financials'].columns[i] if not data_sources['financials'].empty else pd.Timestamp.now()
            
            # Map requested line items to yfinance data
            for item in line_items:
                value = None
                
                if item == "free_cash_flow":
                    # Free Cash Flow = Operating Cash Flow - Capital Expenditures
                    if not data_sources['cashflow'].empty and i < len(data_sources['cashflow'].columns):
                        operating_cf = data_sources['cashflow'].loc[data_sources['cashflow'].index.str.contains('Operating Cash Flow', case=False, na=False), data_sources['cashflow'].columns[i]].values
                        capex = data_sources['cashflow'].loc[data_sources['cashflow'].index.str.contains('Capital Expenditure', case=False, na=False), data_sources['cashflow'].columns[i]].values
                        
                        if len(operating_cf) > 0 and len(capex) > 0:
                            value = float(operating_cf[0] + capex[0])  # capex is usually negative
                        elif len(operating_cf) > 0:
                            value = float(operating_cf[0])
                
                elif item == "net_income":
                    if not data_sources['financials'].empty and i < len(data_sources['financials'].columns):
                        net_income = data_sources['financials'].loc[data_sources['financials'].index.str.contains('Net Income', case=False, na=False), data_sources['financials'].columns[i]].values
                        if len(net_income) > 0:
                            value = float(net_income[0])
                
                elif item == "depreciation_and_amortization":
                    if not data_sources['cashflow'].empty and i < len(data_sources['cashflow'].columns):
                        depr = data_sources['cashflow'].loc[data_sources['cashflow'].index.str.contains('Depreciation', case=False, na=False), data_sources['cashflow'].columns[i]].values
                        if len(depr) > 0:
                            value = float(depr[0])
                
                elif item == "capital_expenditure":
                    if not data_sources['cashflow'].empty and i < len(data_sources['cashflow'].columns):
                        capex = data_sources['cashflow'].loc[data_sources['cashflow'].index.str.contains('Capital Expenditure', case=False, na=False), data_sources['cashflow'].columns[i]].values
                        if len(capex) > 0:
                            value = float(capex[0])
                
                elif item == "working_capital":
                    if not data_sources['balance_sheet'].empty and i < len(data_sources['balance_sheet'].columns):
                        # Working Capital = Current Assets - Current Liabilities
                        current_assets = data_sources['balance_sheet'].loc[data_sources['balance_sheet'].index.str.contains('Current Assets', case=False, na=False), data_sources['balance_sheet'].columns[i]].values
                        current_liab = data_sources['balance_sheet'].loc[data_sources['balance_sheet'].index.str.contains('Current Liabilities', case=False, na=False), data_sources['balance_sheet'].columns[i]].values
                        
                        if len(current_assets) > 0 and len(current_liab) > 0:
                            value = float(current_assets[0] - current_liab[0])
                
                line_item_values[item] = value
            
            # Create LineItem object
            line_item = LineItem(
                ticker=ticker,
                report_period=date_col.strftime('%Y-%m-%d'),
                period=period,
                currency="USD",
                **{item: line_item_values.get(item) for item in line_items}
            )
            results.append(line_item)
        
        # Cache the results
        if results:
            _cache.set_line_items(cache_key, [item.model_dump() for item in results])
        
        return results
        
    except Exception as e:
        print(f"Warning: Could not fetch line items for {ticker} from yfinance: {str(e)}")
        return []


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: Optional[str] = None,
    limit: int = 1000,
    api_key: str = None,
) -> List[InsiderTrade]:
    """Fetch insider trades from cache or return empty list (yfinance doesn't provide insider trades)."""
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_insider_trades(cache_key):
        return [InsiderTrade(**trade) for trade in cached_data]

    # yfinance doesn't provide insider trading data
    # Return empty list and cache it to avoid repeated calls
    print(f"Warning: Insider trading data not available for {ticker} (yfinance doesn't provide this data)")
    
    # Cache empty result to avoid repeated calls
    _cache.set_insider_trades(cache_key, [])
    return []


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: Optional[str] = None,
    limit: int = 1000,
    api_key: str = None,
) -> List[CompanyNews]:
    """Fetch company news from cache or yfinance."""
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_company_news(cache_key):
        return [CompanyNews(**news) for news in cached_data]

    # Fetch from yfinance (limited news capability)
    try:
        stock = yf.Ticker(ticker)
        news_data = stock.news
        
        if not news_data:
            return []
        
        # Convert yfinance news to CompanyNews objects
        all_news = []
        for news_item in news_data[:limit]:  # Limit results
            # Convert timestamp to date string
            publish_time = datetime.datetime.fromtimestamp(news_item.get('providerPublishTime', 0))
            date_str = publish_time.strftime('%Y-%m-%d')
            
            # Skip if outside date range
            if start_date and date_str < start_date:
                continue
            if date_str > end_date:
                continue
            
            news = CompanyNews(
                ticker=ticker,
                title=news_item.get('title', ''),
                author=news_item.get('publisher', ''),
                source=news_item.get('publisher', ''),
                date=date_str,
                url=news_item.get('link', ''),
                sentiment=None  # yfinance doesn't provide sentiment
            )
            all_news.append(news)
        
        # Cache the results using the comprehensive cache key
        _cache.set_company_news(cache_key, [news.model_dump() for news in all_news])
        return all_news
        
    except Exception as e:
        # Return empty list if news fetching fails (yfinance news can be unreliable)
        print(f"Warning: Could not fetch news for {ticker}: {str(e)}")
        return []


def get_market_cap(
    ticker: str,
    end_date: str,
    api_key: str = None,
) -> Optional[float]:
    """Fetch market cap from yfinance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        market_cap = info.get('marketCap')
        
        if market_cap:
            return float(market_cap)
        
        # Fallback: try to get from financial metrics
        financial_metrics = get_financial_metrics(ticker, end_date, api_key=api_key)
        if financial_metrics and financial_metrics[0].market_cap:
            return financial_metrics[0].market_cap
            
        return None
        
    except Exception as e:
        print(f"Error fetching market cap for {ticker}: {str(e)}")
        return None


def prices_to_df(prices: List[Price]) -> pd.DataFrame:
    """Convert prices to a DataFrame."""
    df = pd.DataFrame([p.model_dump() for p in prices])
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    numeric_cols = ["open", "close", "high", "low", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df


# Update the get_price_data function to use the new functions
def get_price_data(ticker: str, start_date: str, end_date: str, api_key: str = None) -> pd.DataFrame:
    prices = get_prices(ticker, start_date, end_date, api_key=api_key)
    return prices_to_df(prices)
