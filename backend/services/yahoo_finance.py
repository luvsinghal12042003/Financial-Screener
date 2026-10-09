import logging
from typing import Dict, Any, List, Optional, Tuple
import requests
import pandas as pd
import numpy as np
import yfinance as yf

from backend.models.schemas import StockQuote, LiveQuote, HistoricalDataPoint, HistoricalResponse, SearchResultItem
from backend.services.cache import cache

logger = logging.getLogger("finance_screener.yahoo_finance")

# Persistent HTTP connection pool for sub-100ms request latency
http_session = requests.Session()
http_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})
adapter = requests.adapters.HTTPAdapter(pool_connections=25, pool_maxsize=50, max_retries=1)
http_session.mount("https://", adapter)
http_session.mount("http://", adapter)


# Curated alias dictionary for instant, zero-latency resolution
COMMON_ALIASES: Dict[str, str] = {
    # Top Indian Equities (NSE)
    "RELIANCE": "RELIANCE.NS",
    "RELIANCE INDUSTRIES": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "TATA CONSULTANCY SERVICES": "TCS.NS",
    "INFY": "INFY.NS",
    "INFOSYS": "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "HDFC": "HDFCBANK.NS",
    "HDFC BANK": "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "ICICI": "ICICIBANK.NS",
    "ICICI BANK": "ICICIBANK.NS",
    "SBIN": "SBIN.NS",
    "SBI": "SBIN.NS",
    "STATE BANK OF INDIA": "SBIN.NS",
    "BHARTIARTL": "BHARTIARTL.NS",
    "AIRTEL": "BHARTIARTL.NS",
    "BHARTI AIRTEL": "BHARTIARTL.NS",
    "TATAMOTORS": "TATAMOTORS.NS",
    "TATA MOTORS": "TATAMOTORS.NS",
    "ITC": "ITC.NS",
    "LT": "LT.NS",
    "LARSEN & TOUBRO": "LT.NS",
    "WIPRO": "WIPRO.NS",
    "MARUTI": "MARUTI.NS",
    "KOTAKBANK": "KOTAKBANK.NS",
    "KOTAK": "KOTAKBANK.NS",
    "ASIANPAINT": "ASIANPAINT.NS",
    "AXISBANK": "AXISBANK.NS",
    "SUNPHARMA": "SUNPHARMA.NS",
    "BAJFINANCE": "BAJFINANCE.NS",
    "TITAN": "TITAN.NS",
    "HCLTECH": "HCLTECH.NS",
    "ADANIENT": "ADANIENT.NS",
    "ADANIPORTS": "ADANIPORTS.NS",
    "NIFTY": "^NSEI",
    "NIFTY 50": "^NSEI",
    "SENSEX": "^BSESN",
    # Top US / Global Equities
    "APPLE": "AAPL",
    "AAPL": "AAPL",
    "MICROSOFT": "MSFT",
    "MSFT": "MSFT",
    "GOOGLE": "GOOGL",
    "ALPHABET": "GOOGL",
    "GOOG": "GOOGL",
    "GOOGL": "GOOGL",
    "AMAZON": "AMZN",
    "AMZN": "AMZN",
    "TESLA": "TSLA",
    "TSLA": "TSLA",
    "NVIDIA": "NVDA",
    "NVDA": "NVDA",
    "META": "META",
    "FACEBOOK": "META",
    "NETFLIX": "NFLX",
    "NFLX": "NFLX",
    "BERKSHIRE": "BRK-B",
    "JPMORGAN": "JPM",
    "JPM": "JPM",
    "VISA": "V",
}

# Cache TTL constants (in seconds)
CACHE_TTL_LIVE = 1         # 1 second for real-time live price ticks
CACHE_TTL_QUOTE = 10       # 10 seconds for stock quote details
CACHE_TTL_HISTORY = 300    # 5 minutes for historical series
CACHE_TTL_SEARCH = 3600    # 1 hour for symbol searches


def normalize_exchange(exchange_str: Optional[str]) -> str:
    if not exchange_str:
        return "N/A"
    clean = exchange_str.upper()
    if clean in ("NSI", "NSE"):
        return "NSE"
    if clean in ("BSE", "BOM"):
        return "BSE"
    if clean in ("NMS", "NGS", "NCM", "NASDAQ"):
        return "NASDAQ"
    if clean in ("NYQ", "NYSE"):
        return "NYSE"
    return clean


def search_symbols(query: str, max_results: int = 8) -> List[SearchResultItem]:
    """
    Searches for symbols matching query using Yahoo's query search API.
    Falls back to yfinance Search.
    """
    query_clean = query.strip()
    if not query_clean:
        return []

    cache_key = f"search:{query_clean.lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    results: List[SearchResultItem] = []

    # Check direct alias first
    upper_q = query_clean.upper()
    if upper_q in COMMON_ALIASES:
        resolved = COMMON_ALIASES[upper_q]
        results.append(
            SearchResultItem(
                ticker=resolved,
                name=query_clean.title(),
                exchange="NSE" if resolved.endswith(".NS") else ("BSE" if resolved.endswith(".BO") else "US"),
                type="EQUITY"
            )
        )

    # Call Yahoo search API
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={requests.utils.quote(query_clean)}&quotesCount={max_results}&newsCount=0"

    try:
        resp = requests.get(url, headers=headers, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            quotes = data.get("quotes", [])
            seen_symbols = {r.ticker for r in results}
            for q in quotes:
                sym = q.get("symbol")
                if not sym or sym in seen_symbols:
                    continue
                quote_type = q.get("quoteType", "EQUITY")
                # Filter out irrelevant types if needed, prioritizing EQUITY, ETF, INDEX
                if quote_type not in ("EQUITY", "ETF", "INDEX", "MUTUALFUND"):
                    continue
                name = q.get("shortname") or q.get("longname") or sym
                exchange = normalize_exchange(q.get("exchange") or q.get("exchDisp"))
                results.append(
                    SearchResultItem(
                        ticker=sym,
                        name=name,
                        exchange=exchange,
                        type=quote_type
                    )
                )
                seen_symbols.add(sym)
    except Exception as e:
        logger.warning(f"Yahoo Search API request error: {e}")

    # If empty, try yfinance Search as secondary fallback
    if not results:
        try:
            yf_search = yf.Search(query_clean)
            for q in getattr(yf_search, "quotes", [])[:max_results]:
                sym = q.get("symbol")
                if sym:
                    results.append(
                        SearchResultItem(
                            ticker=sym,
                            name=q.get("shortname") or q.get("longname") or sym,
                            exchange=normalize_exchange(q.get("exchange")),
                            type=q.get("quoteType", "EQUITY")
                        )
                    )
        except Exception as e:
            logger.warning(f"yfinance Search fallback error: {e}")

    # Fallback heuristic: check if query + .NS or uppercase is feasible
    if not results and query_clean.isalnum():
        results.append(
            SearchResultItem(
                ticker=f"{upper_q}.NS",
                name=f"{upper_q} (NSE India)",
                exchange="NSE",
                type="EQUITY"
            )
        )
        results.append(
            SearchResultItem(
                ticker=upper_q,
                name=upper_q,
                exchange="US",
                type="EQUITY"
            )
        )

    cache.set(cache_key, results, CACHE_TTL_SEARCH)
    return results


def resolve_ticker(query: str) -> str:
    """
    Resolves user query (company name, partial symbol, or ticker) to a valid Yahoo Finance ticker.
    Examples:
      'Reliance' -> 'RELIANCE.NS'
      'RELIANCE' -> 'RELIANCE.NS'
      'AAPL' -> 'AAPL'
      'TCS' -> 'TCS.NS'
    """
    clean = query.strip()
    upper = clean.upper()

    # 1. Direct alias dictionary
    if upper in COMMON_ALIASES:
        return COMMON_ALIASES[upper]

    # 2. Already formatted ticker with suffix like .NS, .BO, ^NSEI, etc.
    if "." in upper or "^" in upper or "=" in upper:
        return upper

    # 3. Check if upper is an exact Indian ticker candidate (e.g. RELIANCE, TCS, INFY)
    # If the symbol has a direct NSE mapping or search returns .NS
    results = search_symbols(clean, max_results=5)
    if results:
        # Prioritize exact match if symbol starts with query
        for res in results:
            if res.ticker.upper() == f"{upper}.NS":
                return res.ticker
            if res.ticker.upper() == upper:
                return res.ticker
        # Otherwise return top search result ticker
        return results[0].ticker

    # 4. Default fallback: return upper
    return upper


def get_fast_live_quote(ticker: str) -> LiveQuote:
    """
    Ultra-fast real-time price fetcher leveraging persistent HTTP connection pool
    to Yahoo's v8 chart endpoint. Designed for 1-second interval live polling.
    Latency is typically 70ms - 150ms.
    """
    resolved_ticker = resolve_ticker(ticker)
    cache_key = f"live:{resolved_ticker}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(resolved_ticker)}?interval=1m&range=1d"
    try:
        resp = http_session.get(url, timeout=2.5)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("chart", {}).get("result", [])
            if results and len(results) > 0:
                meta = results[0].get("meta", {})
                last_price = meta.get("regularMarketPrice") or meta.get("chartPreviousClose")
                prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")
                day_high = meta.get("regularMarketDayHigh")
                day_low = meta.get("regularMarketDayLow")
                volume = meta.get("regularMarketVolume")
                fifty_two_high = meta.get("fiftyTwoWeekHigh")
                fifty_two_low = meta.get("fiftyTwoWeekLow")
                currency = (meta.get("currency") or "USD").upper()
                exchange = normalize_exchange(meta.get("exchangeName"))

                if last_price is not None and not np.isnan(last_price):
                    last_price = round(float(last_price), 2)
                    if prev_close and not np.isnan(prev_close) and float(prev_close) > 0:
                        prev_close = round(float(prev_close), 2)
                        change = round(last_price - prev_close, 2)
                        change_percent = round((change / prev_close) * 100, 2)
                    else:
                        prev_close = last_price
                        change = 0.0
                        change_percent = 0.0

                    live_quote = LiveQuote(
                        ticker=resolved_ticker,
                        price=last_price,
                        change=change,
                        change_percent=change_percent,
                        previous_close=prev_close,
                        day_high=round(float(day_high), 2) if day_high is not None and not np.isnan(day_high) else None,
                        day_low=round(float(day_low), 2) if day_low is not None and not np.isnan(day_low) else None,
                        fifty_two_week_high=round(float(fifty_two_high), 2) if fifty_two_high is not None and not np.isnan(fifty_two_high) else None,
                        fifty_two_week_low=round(float(fifty_two_low), 2) if fifty_two_low is not None and not np.isnan(fifty_two_low) else None,
                        volume=int(volume) if volume is not None and not np.isnan(volume) else None,
                        currency=currency,
                        exchange=exchange,
                        timestamp=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
                    cache.set(cache_key, live_quote, CACHE_TTL_LIVE)
                    return live_quote
    except Exception as e:
        logger.debug(f"Fast live quote endpoint error for {resolved_ticker}: {e}")

    # Fallback to standard quote if v8 fast path is temporarily unreachable
    quote = get_stock_quote(resolved_ticker)
    live_fallback = LiveQuote(
        ticker=quote.ticker,
        price=quote.price,
        change=quote.change,
        change_percent=quote.change_percent,
        previous_close=quote.previous_close,
        day_high=quote.day_high,
        day_low=quote.day_low,
        fifty_two_week_high=quote.fifty_two_week_high,
        fifty_two_week_low=quote.fifty_two_week_low,
        volume=quote.volume,
        currency=quote.currency,
        exchange=quote.exchange,
        timestamp=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    cache.set(cache_key, live_fallback, CACHE_TTL_LIVE)
    return live_fallback


def get_stock_quote(ticker: str) -> StockQuote:
    """
    Fetches real-time / latest price and market information for ticker.
    Utilizes fast persistent HTTP endpoint first for sub-100ms response time,
    with graceful fallback to yfinance.
    """
    resolved_ticker = resolve_ticker(ticker)
    cache_key = f"quote:{resolved_ticker}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Fast path: query persistent session v8 endpoint (sub-100ms)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(resolved_ticker)}?interval=1m&range=1d"
    try:
        resp = http_session.get(url, timeout=2.5)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("chart", {}).get("result", [])
            if results and len(results) > 0:
                meta = results[0].get("meta", {})
                last_price = meta.get("regularMarketPrice") or meta.get("chartPreviousClose")
                if last_price is not None and not np.isnan(last_price):
                    last_price = round(float(last_price), 2)
                    prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")
                    if prev_close and not np.isnan(prev_close) and float(prev_close) > 0:
                        prev_close = round(float(prev_close), 2)
                        change = round(last_price - prev_close, 2)
                        change_percent = round((change / prev_close) * 100, 2)
                    else:
                        prev_close = last_price
                        change = 0.0
                        change_percent = 0.0

                    company_name = meta.get("longName") or meta.get("shortName") or resolved_ticker
                    exchange = normalize_exchange(meta.get("exchangeName"))
                    currency = (meta.get("currency") or "USD").upper()
                    day_high = meta.get("regularMarketDayHigh")
                    day_low = meta.get("regularMarketDayLow")
                    fifty_two_high = meta.get("fiftyTwoWeekHigh")
                    fifty_two_low = meta.get("fiftyTwoWeekLow")
                    market_cap = None
                    pe_ratio = None
                    try:
                        t = yf.Ticker(resolved_ticker)
                        fi = getattr(t, "fast_info", {})
                        if hasattr(fi, "get"):
                            market_cap = fi.get("marketCap")
                            if not fifty_two_high:
                                fifty_two_high = fi.get("yearHigh")
                            if not fifty_two_low:
                                fifty_two_low = fi.get("yearLow")
                        info = getattr(t, "info", {})
                        if isinstance(info, dict):
                            pe_ratio = info.get("trailingPE") or info.get("forwardPE")
                    except Exception:
                        pass

                    quote = StockQuote(
                        ticker=resolved_ticker,
                        company_name=company_name,
                        currency=currency,
                        exchange=exchange,
                        price=last_price,
                        change=change,
                        change_percent=change_percent,
                        previous_close=prev_close,
                        day_high=round(float(day_high), 2) if day_high is not None and not np.isnan(day_high) else None,
                        day_low=round(float(day_low), 2) if day_low is not None and not np.isnan(day_low) else None,
                        fifty_two_week_high=round(float(fifty_two_high), 2) if fifty_two_high is not None and not np.isnan(fifty_two_high) else None,
                        fifty_two_week_low=round(float(fifty_two_low), 2) if fifty_two_low is not None and not np.isnan(fifty_two_low) else None,
                        volume=int(volume) if volume is not None and not np.isnan(volume) else None,
                        market_cap=round(float(market_cap), 2) if market_cap is not None and not np.isnan(market_cap) else None,
                        pe_ratio=round(float(pe_ratio), 2) if pe_ratio is not None and not np.isnan(pe_ratio) else None,
                    )
                    cache.set(cache_key, quote, CACHE_TTL_QUOTE)
                    return quote
    except Exception as e:
        logger.debug(f"Fast quote fetch error for {resolved_ticker}: {e}")

    # Fallback to yfinance ticker inspection
    try:
        t = yf.Ticker(resolved_ticker)
        fast_info = getattr(t, "fast_info", {})
        
        last_price = None
        prev_close = None
        currency = "USD"
        exchange = "N/A"
        day_high = None
        day_low = None
        year_high = None
        year_low = None
        volume = None
        market_cap = None

        if hasattr(fast_info, "get"):
            try:
                last_price = fast_info.get("lastPrice")
                prev_close = fast_info.get("previousClose") or fast_info.get("regularMarketPreviousClose")
                currency = fast_info.get("currency") or "USD"
                exchange = normalize_exchange(fast_info.get("exchange"))
                day_high = fast_info.get("dayHigh")
                day_low = fast_info.get("dayLow")
                year_high = fast_info.get("yearHigh")
                year_low = fast_info.get("yearLow")
                volume = fast_info.get("lastVolume")
                market_cap = fast_info.get("marketCap")
            except (KeyError, IndexError, TypeError):
                last_price = None

        company_name = resolved_ticker
        pe_ratio = None
        try:
            info = t.info
            if isinstance(info, dict) and info.get("symbol"):
                company_name = info.get("longName") or info.get("shortName") or company_name
                if not prev_close:
                    prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
                if last_price is None:
                    last_price = info.get("regularMarketPrice") or info.get("currentPrice")
                if not currency or currency == "USD":
                    currency = info.get("currency") or currency
                if not exchange or exchange == "N/A":
                    exchange = normalize_exchange(info.get("exchange"))
                if day_high is None:
                    day_high = info.get("dayHigh")
                if day_low is None:
                    day_low = info.get("dayLow")
                if year_high is None:
                    year_high = info.get("fiftyTwoWeekHigh")
                if year_low is None:
                    year_low = info.get("fiftyTwoWeekLow")
                if volume is None:
                    volume = info.get("regularMarketVolume") or info.get("volume")
                pe_ratio = info.get("trailingPE") or info.get("forwardPE")
        except Exception as e:
            logger.debug(f"Unable to read extended info for {resolved_ticker}: {e}")

        if last_price is None or pd.isna(last_price):
            try:
                hist = t.history(period="5d")
            except Exception:
                hist = pd.DataFrame()

            if not hist.empty:
                last_price = float(hist["Close"].iloc[-1])
                if len(hist) > 1 and prev_close is None:
                    prev_close = float(hist["Close"].iloc[-2])
                if day_high is None:
                    day_high = float(hist["High"].iloc[-1])
                if day_low is None:
                    day_low = float(hist["Low"].iloc[-1])
                if volume is None:
                    volume = int(hist["Volume"].iloc[-1])
            else:
                raise ValueError(f"No market data available for ticker '{resolved_ticker}'.")

        last_price = round(float(last_price), 2)
        if prev_close and not pd.isna(prev_close) and float(prev_close) > 0:
            prev_close = round(float(prev_close), 2)
            change = round(last_price - prev_close, 2)
            change_percent = round((change / prev_close) * 100, 2)
        else:
            prev_close = last_price
            change = 0.0
            change_percent = 0.0

        quote = StockQuote(
            ticker=resolved_ticker,
            company_name=company_name,
            currency=currency.upper(),
            exchange=exchange,
            price=last_price,
            change=change,
            change_percent=change_percent,
            previous_close=prev_close,
            day_high=round(float(day_high), 2) if day_high is not None and not pd.isna(day_high) else None,
            day_low=round(float(day_low), 2) if day_low is not None and not pd.isna(day_low) else None,
            fifty_two_week_high=round(float(year_high), 2) if year_high is not None and not pd.isna(year_high) else None,
            fifty_two_week_low=round(float(year_low), 2) if year_low is not None and not pd.isna(year_low) else None,
            volume=int(volume) if volume is not None and not pd.isna(volume) else None,
            market_cap=round(float(market_cap), 2) if market_cap is not None and not pd.isna(market_cap) else None,
            pe_ratio=round(float(pe_ratio), 2) if pe_ratio is not None and not pd.isna(pe_ratio) else None,
        )

        cache.set(cache_key, quote, CACHE_TTL_QUOTE)
        return quote
    except ValueError as ve:
        raise ve
    except Exception as e:
        logger.error(f"Error fetching quote for ticker '{resolved_ticker}': {e}")
        if "not found" in str(e).lower() or "delisted" in str(e).lower():
            raise ValueError(f"Ticker '{resolved_ticker}' not found.")
        raise e


def get_history_df(ticker: str, period: str = "1y", interval: str = "1d") -> Tuple[pd.DataFrame, str, str]:
    """
    Fetches raw OHLCV DataFrame for ticker, normalizing period and interval.
    Returns (DataFrame, normalized_period, normalized_interval).
    """
    resolved_ticker = resolve_ticker(ticker)
    
    # Normalize period and interval
    period = period.lower().strip()
    interval = interval.lower().strip()

    valid_periods = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "5y", "max"]
    if period not in valid_periods:
        period = "1y"

    # Choose optimal interval if user didn't specify a custom non-default interval
    if period == "1d":
        if interval in ["1d", "1wk", "1mo"] or interval not in ["1m", "2m", "5m", "15m", "30m", "1h"]:
            interval = "5m"
    elif period == "5d":
        if interval in ["1d", "1wk", "1mo"] or interval not in ["5m", "15m", "30m", "1h"]:
            interval = "15m"
    elif period in ["1mo", "3mo"]:
        if interval in ["1m", "2m", "5m"]:
            interval = "1h"
        elif interval not in ["15m", "30m", "1h", "1d"]:
            interval = "1d"
    elif period in ["6mo", "1y", "5y", "max"]:
        if interval in ["1m", "2m", "5m", "15m", "30m", "1h"]:
            interval = "1d"
        elif interval not in ["1d", "1wk", "1mo"]:
            interval = "1d"

    t = yf.Ticker(resolved_ticker)
    df = t.history(period=period, interval=interval)

    # Cascading fallbacks if market is closed, holiday, or intraday is empty
    if df.empty and period == "1d":
        df = t.history(period="5d", interval="15m")
        if not df.empty:
            period = "5d"
            interval = "15m"

    if df.empty and period in ["1d", "5d"]:
        df = t.history(period="1mo", interval="1d")
        if not df.empty:
            period = "1mo"
            interval = "1d"

    if df.empty:
        # Fallback to 1y daily
        df = t.history(period="1y", interval="1d")
        if not df.empty:
            period = "1y"
            interval = "1d"

    if df.empty:
        raise ValueError(f"Historical data is unavailable for {resolved_ticker}.")

    # Clean DataFrame: ensure standard column names
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.dropna(subset=["Open", "High", "Low", "Close"], inplace=True)
    return df, period, interval


def get_stock_history(
    ticker: str,
    period: str = "1y",
    interval: str = "1d"
) -> HistoricalResponse:
    """
    Fetches normalized historical OHLCV data.
    """
    resolved_ticker = resolve_ticker(ticker)
    cache_key = f"hist:{resolved_ticker}:{period}:{interval}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    df, norm_period, norm_interval = get_history_df(resolved_ticker, period, interval)

    data_points: List[HistoricalDataPoint] = []
    for idx, row in df.iterrows():
        # Handle index date/datetime formatting
        if hasattr(idx, "strftime"):
            if norm_interval in ["1m", "2m", "5m", "15m", "30m", "1h"]:
                date_str = idx.strftime("%Y-%m-%d %H:%M:%S")
            else:
                date_str = idx.strftime("%Y-%m-%d")
        else:
            date_str = str(idx)

        data_points.append(
            HistoricalDataPoint(
                date=date_str,
                open=round(float(row["Open"]), 2),
                high=round(float(row["High"]), 2),
                low=round(float(row["Low"]), 2),
                close=round(float(row["Close"]), 2),
                volume=int(row["Volume"]) if not pd.isna(row["Volume"]) else 0
            )
        )

    # Get quote or metadata
    currency = "USD"
    company_name = resolved_ticker
    try:
        quote = get_stock_quote(resolved_ticker)
        currency = quote.currency
        company_name = quote.company_name
        exchange = quote.exchange
    except Exception:
        exchange = "N/A"

    response = HistoricalResponse(
        ticker=resolved_ticker,
        company_name=company_name,
        currency=currency,
        exchange=exchange,
        period=norm_period,
        interval=norm_interval,
        data=data_points
    )

    cache.set(cache_key, response, CACHE_TTL_HISTORY)
    return response
