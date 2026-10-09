from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class StockQuote(BaseModel):
    ticker: str
    company_name: str
    currency: str = "USD"
    exchange: str = "N/A"
    price: float
    change: float
    change_percent: float
    previous_close: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    volume: Optional[int] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
class LiveQuote(BaseModel):
    ticker: str
    price: float
    change: float
    change_percent: float
    previous_close: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    volume: Optional[int] = None
    currency: Optional[str] = "USD"
    exchange: Optional[str] = "N/A"
    timestamp: Optional[str] = None


class HistoricalDataPoint(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class HistoricalResponse(BaseModel):
    ticker: str
    company_name: Optional[str] = None
    currency: Optional[str] = "USD"
    exchange: Optional[str] = "N/A"
    period: str
    interval: str
    data: List[HistoricalDataPoint]
    indicators: Optional[Dict[str, Any]] = None


class SearchResultItem(BaseModel):
    ticker: str
    name: str
    exchange: Optional[str] = None
    type: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]


class IndicatorInfo(BaseModel):
    id: str
    name: str
    category: str  # "trend", "momentum", "volatility", "volume"
    type: str  # "overlay", "subplot"
    description: str


class IndicatorListResponse(BaseModel):
    indicators: List[IndicatorInfo]


class ErrorResponse(BaseModel):
    detail: str
    suggestions: Optional[List[str]] = None


# -------------------------------------------------------------
# Financial Statements & Fundamental Analysis Models (Phase 2)
# -------------------------------------------------------------
class StatementLineItem(BaseModel):
    name: str
    standard_label: Optional[str] = None
    values: Dict[str, Optional[float]]  # period_date -> numeric_value
    is_derived: bool = False


class FinancialStatementResponse(BaseModel):
    ticker: str
    company_name: str
    statement_type: str  # "income_statement", "balance_sheet", "cash_flow"
    frequency: str       # "annual", "quarterly", "ttm"
    currency: str
    periods: List[str]   # sorted dates: ["2025-03-31", "2024-03-31", ...]
    line_items: List[StatementLineItem]
    source: str = "Yahoo Finance (yfinance)"


class RatioItem(BaseModel):
    id: str
    name: str
    category: str        # "valuation", "profitability", "liquidity", "leverage", "efficiency"
    value: Optional[float]
    unit: str            # "x", "%", "ratio"
    formula: str
    description: str
    period: Optional[str] = None


class FinancialRatiosResponse(BaseModel):
    ticker: str
    company_name: str
    currency: str
    as_of_date: Optional[str] = None
    ratios: List[RatioItem]


class GrowthMetric(BaseModel):
    metric: str
    yoy_growth: Optional[float] = None
    cagr_3y: Optional[float] = None
    cagr_5y: Optional[float] = None
    notes: Optional[str] = None


class GrowthResponse(BaseModel):
    ticker: str
    company_name: str
    currency: str
    periods_analyzed: List[str]
    metrics: List[GrowthMetric]


class EmailRequest(BaseModel):
    email: str


class EmailResponse(BaseModel):
    status: str
    message: str
    email: str
    portal_link: str
    delivery_mode: str
    timestamp: str
    preview_subject: Optional[str] = None
    preview_snippet: Optional[str] = None

