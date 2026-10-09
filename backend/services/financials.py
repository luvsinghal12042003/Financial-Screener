import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd
import yfinance as yf

from backend.models.schemas import (
    StatementLineItem,
    FinancialStatementResponse,
    RatioItem,
    FinancialRatiosResponse,
    GrowthMetric,
    GrowthResponse,
)
from backend.services.cache import cache
from backend.services.yahoo_finance import resolve_ticker, get_stock_quote

logger = logging.getLogger("finance_screener.financials")

# Cache TTL for financial statements (1 hour)
CACHE_TTL_FINANCIALS = 3600

# Mapping common reported items to standardized display labels
STANDARD_LABEL_MAP: Dict[str, str] = {
    # Income Statement
    "Total Revenue": "Total Revenue",
    "Operating Revenue": "Total Revenue",
    "Revenue": "Total Revenue",
    "Cost Of Revenue": "Cost of Revenue",
    "Reconciled Cost Of Revenue": "Cost of Revenue",
    "Gross Profit": "Gross Profit",
    "Operating Income": "Operating Income (EBIT)",
    "Operating Profit": "Operating Income (EBIT)",
    "EBIT": "Operating Income (EBIT)",
    "EBITDA": "EBITDA",
    "Normalized EBITDA": "Normalized EBITDA",
    "Net Income": "Net Income (PAT)",
    "Net Income Common Stockholders": "Net Income (PAT)",
    "Net Income From Continuing And Discontinued Operation": "Net Income (PAT)",
    "Diluted EPS": "Diluted EPS",
    "Basic EPS": "Basic EPS",
    "Tax Provision": "Tax Provision",
    "Pretax Income": "Profit Before Tax (PBT)",
    "Interest Expense": "Interest Expense",
    # Balance Sheet
    "Total Assets": "Total Assets",
    "Current Assets": "Total Current Assets",
    "Total Liabilities Net Minority Interest": "Total Liabilities",
    "Total Liabilities": "Total Liabilities",
    "Current Liabilities": "Total Current Liabilities",
    "Stockholders Equity": "Shareholders' Equity",
    "Common Stock Equity": "Shareholders' Equity",
    "Total Equity": "Shareholders' Equity",
    "Total Debt": "Total Debt",
    "Long Term Debt": "Long-Term Debt",
    "Cash And Cash Equivalents": "Cash & Cash Equivalents",
    "Cash Cash Equivalents And Short Term Investments": "Cash & Cash Equivalents",
    "Working Capital": "Working Capital",
    "Invested Capital": "Invested Capital",
    # Cash Flow Statement
    "Operating Cash Flow": "Cash Flow from Operations (CFO)",
    "Cash Flow From Continuing Operating Activities": "Cash Flow from Operations (CFO)",
    "Capital Expenditure": "Capital Expenditure (CapEx)",
    "Capital Expenditure Reported": "Capital Expenditure (CapEx)",
    "Free Cash Flow": "Free Cash Flow (FCF)",
    "Investing Cash Flow": "Cash Flow from Investing (CFI)",
    "Financing Cash Flow": "Cash Flow from Financing (CFF)",
}


def _safe_float(val: Any) -> Optional[float]:
    """Converts a value to float, handling NaN, Inf, None and rounding safely."""
    if val is None or pd.isna(val):
        return None
    try:
        f = float(val)
        if np.isinf(f) or np.isnan(f):
            return None
        return round(f, 2)
    except (ValueError, TypeError):
        return None


def _format_date(col: Any) -> str:
    """Formats a pandas Timestamp or date object to YYYY-MM-DD string."""
    if hasattr(col, "strftime"):
        return col.strftime("%Y-%m-%d")
    return str(col)[:10]


def _build_statement_response(
    ticker: str,
    company_name: str,
    statement_type: str,
    frequency: str,
    currency: str,
    df: pd.DataFrame
) -> FinancialStatementResponse:
    """Converts a pandas financial DataFrame into a JSON-safe FinancialStatementResponse."""
    if df is None or df.empty:
        return FinancialStatementResponse(
            ticker=ticker,
            company_name=company_name,
            statement_type=statement_type,
            frequency=frequency,
            currency=currency,
            periods=[],
            line_items=[],
        )

    # Sort columns chronologically descending (latest first)
    cols = sorted(df.columns, reverse=True)
    periods = [_format_date(c) for c in cols]

    line_items: List[StatementLineItem] = []
    for idx in df.index:
        name_str = str(idx).strip()
        standard_label = STANDARD_LABEL_MAP.get(name_str)
        values_dict: Dict[str, Optional[float]] = {}
        for c in cols:
            p_date = _format_date(c)
            val = df.loc[idx, c] if c in df.columns else None
            # If multiple rows match same index name, take first
            if isinstance(val, pd.Series):
                val = val.iloc[0]
            values_dict[p_date] = _safe_float(val)

        line_items.append(
            StatementLineItem(
                name=name_str,
                standard_label=standard_label,
                values=values_dict,
                is_derived=False
            )
        )

    return FinancialStatementResponse(
        ticker=ticker,
        company_name=company_name,
        statement_type=statement_type,
        frequency=frequency,
        currency=currency,
        periods=periods,
        line_items=line_items,
    )


def _compute_ttm_statement(quarterly_df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes TTM by summing the 4 most recent quarterly periods for flow items.
    Requires at least 4 quarterly periods.
    """
    if quarterly_df is None or quarterly_df.empty or len(quarterly_df.columns) < 4:
        raise ValueError("Insufficient quarterly history to derive TTM statement (requires 4 quarters).")

    # Take 4 most recent quarters
    sorted_cols = sorted(quarterly_df.columns, reverse=True)[:4]
    latest_q = sorted_cols[0]
    ttm_date_label = f"TTM ({_format_date(latest_q)})"

    # Sum across the 4 quarters for each line item
    sub_df = quarterly_df[sorted_cols]
    ttm_series = sub_df.sum(axis=1, min_count=1)
    ttm_df = pd.DataFrame({ttm_date_label: ttm_series})
    return ttm_df


def get_financial_statement(
    ticker: str,
    statement_type: str,
    frequency: str = "annual"
) -> FinancialStatementResponse:
    """
    Fetches and normalizes an Income Statement, Balance Sheet, or Cash Flow.
    statement_type: 'income_statement', 'balance_sheet', 'cash_flow'
    frequency: 'annual', 'quarterly', 'ttm'
    """
    resolved_ticker = resolve_ticker(ticker)
    freq = frequency.lower().strip()
    if freq not in ("annual", "quarterly", "ttm"):
        freq = "annual"

    cache_key = f"fin:{resolved_ticker}:{statement_type}:{freq}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Retrieve base stock info for metadata
    quote = get_stock_quote(resolved_ticker)
    company_name = quote.company_name
    currency = quote.currency

    t = yf.Ticker(resolved_ticker)

    df: Optional[pd.DataFrame] = None

    if statement_type == "income_statement":
        if freq == "annual":
            df = getattr(t, "income_stmt", None)
        elif freq == "quarterly":
            df = getattr(t, "quarterly_income_stmt", None)
        elif freq == "ttm":
            q_df = getattr(t, "quarterly_income_stmt", None)
            df = _compute_ttm_statement(q_df)

    elif statement_type == "balance_sheet":
        if freq == "annual":
            df = getattr(t, "balance_sheet", None)
        elif freq == "quarterly":
            df = getattr(t, "quarterly_balance_sheet", None)
        elif freq == "ttm":
            # For balance sheet, TTM represents latest reported quarterly position
            q_df = getattr(t, "quarterly_balance_sheet", None)
            if q_df is not None and not q_df.empty:
                latest_col = sorted(q_df.columns, reverse=True)[0]
                df = q_df[[latest_col]].copy()
                df.columns = [f"Latest Quarter ({_format_date(latest_col)})"]
            else:
                raise ValueError("Quarterly balance sheet unavailable to compute TTM snapshot.")

    elif statement_type == "cash_flow":
        if freq == "annual":
            df = getattr(t, "cashflow", None)
        elif freq == "quarterly":
            df = getattr(t, "quarterly_cashflow", None)
        elif freq == "ttm":
            q_df = getattr(t, "quarterly_cashflow", None)
            df = _compute_ttm_statement(q_df)
    else:
        raise ValueError(f"Unknown statement type '{statement_type}'.")

    if df is None or df.empty:
        raise ValueError(f"{statement_type.replace('_', ' ').title()} data is unavailable for {resolved_ticker} with frequency='{freq}'.")

    resp = _build_statement_response(
        ticker=resolved_ticker,
        company_name=company_name,
        statement_type=statement_type,
        frequency=freq,
        currency=currency,
        df=df
    )

    cache.set(cache_key, resp, CACHE_TTL_FINANCIALS)
    return resp


def _find_item_value(df: pd.DataFrame, target_keys: List[str], col: Any) -> Optional[float]:
    """Helper to locate a value in a DataFrame given a list of possible index synonyms."""
    if df is None or df.empty or col not in df.columns:
        return None
    for key in target_keys:
        for idx in df.index:
            if key.lower() == str(idx).lower():
                val = df.loc[idx, col]
                if isinstance(val, pd.Series):
                    val = val.iloc[0]
                return _safe_float(val)
    return None


def calculate_financial_ratios(ticker: str) -> FinancialRatiosResponse:
    """
    Computes key financial valuation, profitability, liquidity, and leverage ratios.
    Uses latest reported statements and average opening/closing balances where applicable.
    """
    resolved_ticker = resolve_ticker(ticker)
    cache_key = f"ratios:{resolved_ticker}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    quote = get_stock_quote(resolved_ticker)
    company_name = quote.company_name
    currency = quote.currency
    current_price = quote.price

    t = yf.Ticker(resolved_ticker)
    income_stmt = getattr(t, "income_stmt", None)
    balance_sheet = getattr(t, "balance_sheet", None)
    cash_flow = getattr(t, "cashflow", None)
    info = getattr(t, "info", {})

    ratios: List[RatioItem] = []

    # Identify latest and prior annual period columns
    inc_cols = sorted(income_stmt.columns, reverse=True) if income_stmt is not None and not income_stmt.empty else []
    bs_cols = sorted(balance_sheet.columns, reverse=True) if balance_sheet is not None and not balance_sheet.empty else []
    cf_cols = sorted(cash_flow.columns, reverse=True) if cash_flow is not None and not cash_flow.empty else []

    latest_inc_col = inc_cols[0] if inc_cols else None
    latest_bs_col = bs_cols[0] if bs_cols else None
    prior_bs_col = bs_cols[1] if len(bs_cols) > 1 else None
    latest_cf_col = cf_cols[0] if cf_cols else None

    period_str = _format_date(latest_inc_col or latest_bs_col or "Latest")

    # 1. P/E Ratio
    pe_val = quote.pe_ratio
    trailing_eps = _safe_float(info.get("trailingEps")) if isinstance(info, dict) else None
    if pe_val is None and trailing_eps and trailing_eps > 0 and current_price:
        pe_val = round(current_price / trailing_eps, 2)
    ratios.append(
        RatioItem(
            id="PE",
            name="Price to Earnings (P/E)",
            category="valuation",
            value=_safe_float(pe_val),
            unit="x",
            formula="Current Share Price / Trailing 12-Month EPS",
            description="Measures how much investors are paying per dollar/rupee of earnings.",
            period=period_str
        )
    )

    # 2. P/B Ratio
    book_val_per_share = _safe_float(info.get("bookValue")) if isinstance(info, dict) else None
    pb_val = _safe_float(info.get("priceToBook")) if isinstance(info, dict) else None
    if pb_val is None and book_val_per_share and book_val_per_share > 0 and current_price:
        pb_val = round(current_price / book_val_per_share, 2)
    ratios.append(
        RatioItem(
            id="PB",
            name="Price to Book (P/B)",
            category="valuation",
            value=_safe_float(pb_val),
            unit="x",
            formula="Current Share Price / Book Value Per Share",
            description="Compares the market value of the company to its reported book value.",
            period=period_str
        )
    )

    # 3. Revenue, Operating Income & Net Income
    revenue = _find_item_value(income_stmt, ["Total Revenue", "Operating Revenue", "Revenue"], latest_inc_col)
    op_income = _find_item_value(income_stmt, ["Operating Income", "Operating Profit", "EBIT"], latest_inc_col)
    net_income = _find_item_value(income_stmt, ["Net Income", "Net Income Common Stockholders"], latest_inc_col)

    # 4. Operating Margin & Net Profit Margin
    op_margin = None
    if op_income is not None and revenue and revenue > 0:
        op_margin = round((op_income / revenue) * 100, 2)
    ratios.append(
        RatioItem(
            id="OP_MARGIN",
            name="Operating Margin",
            category="profitability",
            value=op_margin,
            unit="%",
            formula="(Operating Income / Total Revenue) * 100",
            description="Percentage of revenue left over after paying wages, raw materials, and other operating costs.",
            period=period_str
        )
    )

    net_margin = None
    if net_income is not None and revenue and revenue > 0:
        net_margin = round((net_income / revenue) * 100, 2)
    ratios.append(
        RatioItem(
            id="NET_MARGIN",
            name="Net Profit Margin",
            category="profitability",
            value=net_margin,
            unit="%",
            formula="(Net Income / Total Revenue) * 100",
            description="Percentage of revenue that translates into bottom-line profit after all expenses and taxes.",
            period=period_str
        )
    )

    # 5. Return on Equity (ROE) & Return on Assets (ROA)
    equity_latest = _find_item_value(balance_sheet, ["Stockholders Equity", "Common Stock Equity", "Total Equity"], latest_bs_col)
    equity_prior = _find_item_value(balance_sheet, ["Stockholders Equity", "Common Stock Equity", "Total Equity"], prior_bs_col)
    avg_equity = (equity_latest + equity_prior) / 2 if (equity_latest and equity_prior) else equity_latest

    roe_val = None
    if net_income is not None and avg_equity and avg_equity > 0:
        roe_val = round((net_income / avg_equity) * 100, 2)
    ratios.append(
        RatioItem(
            id="ROE",
            name="Return on Equity (ROE)",
            category="profitability",
            value=roe_val,
            unit="%",
            formula="(Net Income / Average Shareholders' Equity) * 100",
            description="Measures how efficiently management generates profits using shareholders' invested equity.",
            period=period_str
        )
    )

    assets_latest = _find_item_value(balance_sheet, ["Total Assets"], latest_bs_col)
    assets_prior = _find_item_value(balance_sheet, ["Total Assets"], prior_bs_col)
    avg_assets = (assets_latest + assets_prior) / 2 if (assets_latest and assets_prior) else assets_latest

    roa_val = None
    if net_income is not None and avg_assets and avg_assets > 0:
        roa_val = round((net_income / avg_assets) * 100, 2)
    ratios.append(
        RatioItem(
            id="ROA",
            name="Return on Assets (ROA)",
            category="profitability",
            value=roa_val,
            unit="%",
            formula="(Net Income / Average Total Assets) * 100",
            description="Measures how effectively a company converts its assets into bottom-line net profit.",
            period=period_str
        )
    )

    # 6. Current Ratio
    curr_assets = _find_item_value(balance_sheet, ["Current Assets"], latest_bs_col)
    curr_liab = _find_item_value(balance_sheet, ["Current Liabilities"], latest_bs_col)
    curr_ratio = None
    if curr_assets is not None and curr_liab and curr_liab > 0:
        curr_ratio = round(curr_assets / curr_liab, 2)
    ratios.append(
        RatioItem(
            id="CURRENT_RATIO",
            name="Current Ratio",
            category="liquidity",
            value=curr_ratio,
            unit="ratio",
            formula="Total Current Assets / Total Current Liabilities",
            description="Measures short-term liquidity and ability to cover obligations due within one year.",
            period=period_str
        )
    )

    # 7. Debt to Equity
    total_debt = _find_item_value(balance_sheet, ["Total Debt", "Long Term Debt And Capital Lease Obligation"], latest_bs_col)
    debt_equity = None
    if total_debt is not None and equity_latest and equity_latest > 0:
        debt_equity = round(total_debt / equity_latest, 2)
    ratios.append(
        RatioItem(
            id="DEBT_EQUITY",
            name="Debt to Equity",
            category="leverage",
            value=debt_equity,
            unit="ratio",
            formula="Total Debt / Total Shareholders' Equity",
            description="Quantifies financial leverage by comparing total borrowed debt against net equity.",
            period=period_str
        )
    )

    # 8. Asset Turnover
    asset_turnover = None
    if revenue is not None and avg_assets and avg_assets > 0:
        asset_turnover = round(revenue / avg_assets, 2)
    ratios.append(
        RatioItem(
            id="ASSET_TURNOVER",
            name="Asset Turnover",
            category="efficiency",
            value=asset_turnover,
            unit="x",
            formula="Total Revenue / Average Total Assets",
            description="Measures how efficiently a company deploys its total asset base to generate revenue.",
            period=period_str
        )
    )

    # 9. CFO / PAT (Operating Cash Flow to Profit After Tax)
    cfo = _find_item_value(cash_flow, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"], latest_cf_col)
    cfo_pat = None
    if cfo is not None and net_income and net_income != 0:
        cfo_pat = round(cfo / net_income, 2)
    ratios.append(
        RatioItem(
            id="CFO_PAT",
            name="CFO / PAT",
            category="efficiency",
            value=cfo_pat,
            unit="ratio",
            formula="Operating Cash Flow / Net Income (PAT)",
            description="Evaluates earnings quality: values above 1.0 indicate profits are strongly backed by actual cash inflows.",
            period=period_str
        )
    )

    # 10. Free Cash Flow
    capex = _find_item_value(cash_flow, ["Capital Expenditure", "Capital Expenditure Reported"], latest_cf_col)
    fcf_reported = _find_item_value(cash_flow, ["Free Cash Flow"], latest_cf_col)
    fcf = fcf_reported
    if fcf is None and cfo is not None and capex is not None:
        # Note: In cash flow statements, Capex is conventionally negative
        fcf = cfo + capex if capex < 0 else cfo - capex
    ratios.append(
        RatioItem(
            id="FCF",
            name="Free Cash Flow (FCF)",
            category="profitability",
            value=_safe_float(fcf),
            unit=currency,
            formula="Operating Cash Flow - Capital Expenditure",
            description="Cash generated that is freely available for expansion, debt repayment, or dividends.",
            period=period_str
        )
    )

    resp = FinancialRatiosResponse(
        ticker=resolved_ticker,
        company_name=company_name,
        currency=currency,
        as_of_date=period_str,
        ratios=ratios
    )
    cache.set(cache_key, resp, CACHE_TTL_FINANCIALS)
    return resp


def calculate_growth_analysis(ticker: str) -> GrowthResponse:
    """
    Computes YoY and CAGR (3-Year and 5-Year) growth metrics for Revenue and Net Profit.
    Handles negative, zero or missing base values conservatively.
    """
    resolved_ticker = resolve_ticker(ticker)
    cache_key = f"growth:{resolved_ticker}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    quote = get_stock_quote(resolved_ticker)
    company_name = quote.company_name
    currency = quote.currency

    t = yf.Ticker(resolved_ticker)
    income_stmt = getattr(t, "income_stmt", None)

    metrics: List[GrowthMetric] = []
    periods_analyzed: List[str] = []

    if income_stmt is None or income_stmt.empty:
        return GrowthResponse(
            ticker=resolved_ticker,
            company_name=company_name,
            currency=currency,
            periods_analyzed=[],
            metrics=[]
        )

    # Sort columns chronologically descending (latest first: 0=latest, 1=prior, ...)
    cols = sorted(income_stmt.columns, reverse=True)
    periods_analyzed = [_format_date(c) for c in cols]

    def _compute_cagr(start_val: Optional[float], end_val: Optional[float], years: int) -> Tuple[Optional[float], Optional[str]]:
        if start_val is None or end_val is None:
            return None, "Incomplete historical data"
        if start_val <= 0:
            return None, "Base period value is zero or negative (CAGR mathematically undefined)"
        if end_val <= 0:
            return None, "Final period value is zero or negative (CAGR mathematically undefined)"
        try:
            cagr = ((end_val / start_val) ** (1.0 / years) - 1.0) * 100.0
            return round(cagr, 2), None
        except Exception as e:
            return None, str(e)

    # Analyze Revenue Growth
    rev_values = [_find_item_value(income_stmt, ["Total Revenue", "Operating Revenue", "Revenue"], c) for c in cols]
    rev_yoy = None
    if len(rev_values) >= 2 and rev_values[0] is not None and rev_values[1] and rev_values[1] > 0:
        rev_yoy = round(((rev_values[0] - rev_values[1]) / abs(rev_values[1])) * 100.0, 2)

    rev_cagr_3y = None
    rev_3y_note = None
    if len(rev_values) >= 4:
        rev_cagr_3y, rev_3y_note = _compute_cagr(rev_values[3], rev_values[0], 3)
    else:
        rev_3y_note = "Requires at least 4 annual periods"

    rev_cagr_5y = None
    rev_5y_note = None
    if len(rev_values) >= 6:
        rev_cagr_5y, rev_5y_note = _compute_cagr(rev_values[5], rev_values[0], 5)
    else:
        rev_5y_note = "Requires at least 6 annual periods"

    metrics.append(
        GrowthMetric(
            metric="Revenue Growth",
            yoy_growth=rev_yoy,
            cagr_3y=rev_cagr_3y,
            cagr_5y=rev_cagr_5y,
            notes=rev_5y_note or rev_3y_note
        )
    )

    # Analyze Net Profit Growth
    np_values = [_find_item_value(income_stmt, ["Net Income", "Net Income Common Stockholders"], c) for c in cols]
    np_yoy = None
    if len(np_values) >= 2 and np_values[0] is not None and np_values[1] and np_values[1] != 0:
        np_yoy = round(((np_values[0] - np_values[1]) / abs(np_values[1])) * 100.0, 2)

    np_cagr_3y = None
    np_3y_note = None
    if len(np_values) >= 4:
        np_cagr_3y, np_3y_note = _compute_cagr(np_values[3], np_values[0], 3)
    else:
        np_3y_note = "Requires at least 4 annual periods"

    np_cagr_5y = None
    np_5y_note = None
    if len(np_values) >= 6:
        np_cagr_5y, np_5y_note = _compute_cagr(np_values[5], np_values[0], 5)
    else:
        np_5y_note = "Requires at least 6 annual periods"

    metrics.append(
        GrowthMetric(
            metric="Net Profit (PAT) Growth",
            yoy_growth=np_yoy,
            cagr_3y=np_cagr_3y,
            cagr_5y=np_cagr_5y,
            notes=np_5y_note or np_3y_note
        )
    )

    resp = GrowthResponse(
        ticker=resolved_ticker,
        company_name=company_name,
        currency=currency,
        periods_analyzed=periods_analyzed,
        metrics=metrics
    )
    cache.set(cache_key, resp, CACHE_TTL_FINANCIALS)
    return resp
