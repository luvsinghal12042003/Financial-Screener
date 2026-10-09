import os
import logging
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from backend.models.schemas import (
    StockQuote,
    LiveQuote,
    HistoricalResponse,
    SearchResponse,
    IndicatorListResponse,
    ErrorResponse,
    FinancialStatementResponse,
    FinancialRatiosResponse,
    GrowthResponse,
    EmailRequest,
    EmailResponse,
)
from backend.services.yahoo_finance import (
    get_stock_quote,
    get_fast_live_quote,
    get_stock_history,
    get_history_df,
    search_symbols,
    resolve_ticker,
)
from backend.services.indicators import (
    SUPPORTED_INDICATORS,
    compute_requested_indicators,
)
from backend.services.financials import (
    get_financial_statement,
    calculate_financial_ratios,
    calculate_growth_analysis,
)
from backend.services.mailer import (
    send_portal_access_email,
    get_subscribers_list,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("finance_screener.api")

app = FastAPI(
    title="Equity Finance Screener API",
    description="Phase 1: Interactive Equity Market Charting Tool",
    version="1.0.0"
)

# Enable CORS for local development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Custom Exception Handlers to prevent leaking stack traces
# ---------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Market data service error. Please try again later."}
    )


# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------
@app.get("/api/stock/{ticker}", response_model=StockQuote)
async def get_stock(ticker: str):
    """
    Returns real-time/latest price and basic information for a stock.
    Supports symbols (AAPL, RELIANCE.NS) and company names (Reliance, Apple).
    """
    try:
        quote = get_stock_quote(ticker)
        return quote
    except ValueError as ve:
        logger.warning(f"Stock not found for ticker '{ticker}': {ve}")
        raise HTTPException(
            status_code=404,
            detail="We couldn't find this ticker. Try: AAPL, RELIANCE.NS, TCS.NS"
        )
    except Exception as e:
        logger.error(f"Error fetching stock data for '{ticker}': {e}")
        raise HTTPException(
            status_code=503,
            detail="Market data is temporarily unavailable. Please try again."
        )


@app.get("/api/stock/{ticker}/live", response_model=LiveQuote)
async def get_stock_live(ticker: str):
    """
    Ultra-fast real-time price endpoint designed for 1-second interval polling.
    Returns latest traded price, day high/low, volume, and percentage change in ~100ms.
    """
    try:
        live = get_fast_live_quote(ticker)
        return live
    except ValueError as ve:
        logger.warning(f"Stock not found for live ticker '{ticker}': {ve}")
        raise HTTPException(
            status_code=404,
            detail="We couldn't find this ticker."
        )
    except Exception as e:
        logger.error(f"Error fetching live quote for '{ticker}': {e}")
        raise HTTPException(
            status_code=503,
            detail="Live market data is temporarily unavailable."
        )



@app.get("/api/history/{ticker}", response_model=HistoricalResponse)
async def get_history(
    ticker: str,
    period: str = Query(default="1y", description="Time period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 5y, max"),
    interval: str = Query(default="1d", description="Interval: 1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo"),
    indicators: Optional[str] = Query(default=None, description="Comma-separated indicator IDs, e.g. 'SMA_20,SMA_50,RSI,BB'")
):
    """
    Returns historical OHLCV chart data, optionally with computed technical indicators.
    """
    try:
        resolved = resolve_ticker(ticker)
        df, norm_period, norm_interval = get_history_df(resolved, period, interval)

        # Base history response
        history_resp = get_stock_history(resolved, norm_period, norm_interval)

        # Compute technical indicators if requested
        if indicators:
            ind_list = [i.strip() for i in indicators.split(",") if i.strip()]
            computed = compute_requested_indicators(df, ind_list)
            history_resp.indicators = computed

        return history_resp
    except ValueError as ve:
        logger.warning(f"History not available for '{ticker}' with period='{period}': {ve}")
        raise HTTPException(
            status_code=404,
            detail="Historical data is unavailable for this period."
        )
    except Exception as e:
        logger.error(f"Error retrieving history for '{ticker}': {e}")
        raise HTTPException(
            status_code=503,
            detail="Market data is temporarily unavailable. Please try again."
        )


@app.get("/api/indicators/available", response_model=IndicatorListResponse)
async def list_available_indicators():
    """
    Returns metadata for all supported technical indicators.
    """
    return IndicatorListResponse(indicators=SUPPORTED_INDICATORS)


@app.get("/api/indicators/{ticker}")
async def get_indicators_data(
    ticker: str,
    period: str = Query(default="1y"),
    interval: str = Query(default="1d"),
    indicators: str = Query(..., description="Comma-separated indicator IDs (e.g. SMA_20,RSI,BB)")
):
    """
    Calculates technical indicators on demand for the specified ticker and period.
    """
    try:
        resolved = resolve_ticker(ticker)
        df, _, _ = get_history_df(resolved, period, interval)
        ind_list = [i.strip() for i in indicators.split(",") if i.strip()]
        computed = compute_requested_indicators(df, ind_list)
        return {
            "ticker": resolved,
            "period": period,
            "indicators": computed
        }
    except Exception as e:
        logger.error(f"Error calculating indicators for '{ticker}': {e}")
        raise HTTPException(
            status_code=503,
            detail="Unable to calculate indicators. Please verify data availability."
        )


@app.get("/api/search", response_model=SearchResponse)
async def search(q: str = Query(..., min_length=1, description="Company name or ticker query")):
    """
    Auto-complete search endpoint to resolve company names or tickers.
    """
    try:
        results = search_symbols(q)
        return SearchResponse(query=q, results=results)
    except Exception as e:
        logger.error(f"Search failed for '{q}': {e}")
        return SearchResponse(query=q, results=[])


# ---------------------------------------------------------
# Phase 2: Company Financials & Fundamental Analysis Endpoints
# ---------------------------------------------------------
@app.get("/api/financials/{ticker}/income-statement", response_model=FinancialStatementResponse)
async def get_income_statement_endpoint(
    ticker: str,
    frequency: str = Query(default="annual", description="'annual', 'quarterly', or 'ttm'")
):
    """
    Returns normalized Income Statement with reported line items, periods, and currency.
    """
    try:
        stmt = get_financial_statement(ticker, "income_statement", frequency)
        return stmt
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error fetching income statement for '{ticker}': {e}")
        raise HTTPException(status_code=503, detail="Income statement data is temporarily unavailable.")


@app.get("/api/financials/{ticker}/balance-sheet", response_model=FinancialStatementResponse)
async def get_balance_sheet_endpoint(
    ticker: str,
    frequency: str = Query(default="annual", description="'annual', 'quarterly', or 'ttm'")
):
    """
    Returns normalized Balance Sheet statement with reported assets, liabilities, and equity.
    """
    try:
        stmt = get_financial_statement(ticker, "balance_sheet", frequency)
        return stmt
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error fetching balance sheet for '{ticker}': {e}")
        raise HTTPException(status_code=503, detail="Balance sheet data is temporarily unavailable.")


@app.get("/api/financials/{ticker}/cash-flow", response_model=FinancialStatementResponse)
async def get_cash_flow_endpoint(
    ticker: str,
    frequency: str = Query(default="annual", description="'annual', 'quarterly', or 'ttm'")
):
    """
    Returns normalized Cash Flow statement with Operating, Investing, and Financing activities.
    """
    try:
        stmt = get_financial_statement(ticker, "cash_flow", frequency)
        return stmt
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error fetching cash flow statement for '{ticker}': {e}")
        raise HTTPException(status_code=503, detail="Cash flow statement data is temporarily unavailable.")


@app.get("/api/financials/{ticker}/ratios", response_model=FinancialRatiosResponse)
async def get_ratios_endpoint(ticker: str):
    """
    Computes and returns core valuation, profitability, liquidity, and leverage ratios.
    """
    try:
        ratios = calculate_financial_ratios(ticker)
        return ratios
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error calculating financial ratios for '{ticker}': {e}")
        raise HTTPException(status_code=503, detail="Financial ratios are temporarily unavailable.")


@app.get("/api/financials/{ticker}/growth", response_model=GrowthResponse)
async def get_growth_endpoint(ticker: str):
    """
    Computes YoY growth and 3-Year / 5-Year CAGR for Revenue and Net Profit.
    """
    try:
        growth = calculate_growth_analysis(ticker)
        return growth
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error calculating growth analysis for '{ticker}': {e}")
        raise HTTPException(status_code=503, detail="Growth analysis data is temporarily unavailable.")


# ---------------------------------------------------------
# Launch Page & Email Dispatch Endpoints
# ---------------------------------------------------------
@app.post("/api/send-portal-link", response_model=EmailResponse)
async def send_portal_link(req: EmailRequest, request: Request):
    """
    Accepts user email, generates direct portal link, and dispatches invitation email.
    Supports real SMTP when configured or simulated local delivery in development.
    """
    try:
        base_url = str(request.base_url).rstrip("/")
        result = send_portal_access_email(req.email, base_url=base_url)
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error dispatching portal link to '{req.email}': {e}")
        raise HTTPException(status_code=500, detail="Failed to send portal link. Please try again.")


@app.get("/api/launch-subscribers")
async def get_subscribers():
    """
    Returns list of subscriber access requests.
    """
    return {"subscribers": get_subscribers_list()}


# ---------------------------------------------------------
# Static Frontend Serving
# ---------------------------------------------------------
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    async def serve_index():
        response = FileResponse(os.path.join(frontend_dir, "index.html"))
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        return response

    @app.get("/launch")
    async def serve_launch():
        launch_file = os.path.join(frontend_dir, "launch.html")
        if os.path.exists(launch_file):
            response = FileResponse(launch_file)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
            return response
        raise HTTPException(status_code=404, detail="Launch page not found.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
