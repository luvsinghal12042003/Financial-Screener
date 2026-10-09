# Equity Finance Screener — Interactive Market Charting & Fundamental Analysis

An institutional-grade, full-stack equity charting and financial statement analysis web application built with **FastAPI**, **yfinance**, **Pandas**, **NumPy**, and **Plotly.js**.

This project implements **Phase 1 (Interactive Market Charting)** and **Phase 2 (Company Financial Statements & Fundamental Analysis)** of an upcoming **Equity Finance Screener Platform**, engineered for high scalability, real-time live price streaming, server-side technical indicators, standardized financial statements, ratio calculations, and CAGR growth analysis.

---

## Architecture Overview

```text
finance-screener/
│
├── backend/
│   ├── main.py                     # FastAPI application & REST routing
│   ├── requirements.txt            # Python dependencies
│   ├── services/
│   │   ├── yahoo_finance.py        # yfinance integration, ticker resolution & live quote polling
│   │   ├── indicators.py           # NumPy/Pandas technical indicator formulas
│   │   ├── financials.py           # Statements normalization, TTM engine, ratios & growth
│   │   └── cache.py                # In-memory thread-safe TTL cache (Redis-ready)
│   └── models/
│       └── schemas.py              # Pydantic data schemas for quotes, charts & financials
│
├── frontend/
│   ├── index.html                  # Terminal-style financial interface
│   ├── styles.css                  # Dark-first theme, responsive grid & typography
│   └── app.js                      # Plotly.js charting, financials UI & asynchronous UX
│
├── tests/
│   └── test_financials.py          # Unit & integration tests for normalization, ratios & growth
│
└── README.md
```

---

## Phase 1 Features: Market Charting

- **Company & Ticker Resolution**:
  - Direct ticker entry (`AAPL`, `MSFT`, `RELIANCE.NS`, `TCS.NS`, `INFY.NS`).
  - Natural name resolution (`Reliance` &rarr; `RELIANCE.NS`, `TCS` &rarr; `TCS.NS`, `Apple` &rarr; `AAPL`).
  - Autocomplete search with exchange & asset type tags.
  - Suffix support for Indian bourses: `.NS` (National Stock Exchange) and `.BO` (Bombay Stock Exchange).
- **Interactive Price Charting (Plotly.js)**:
  - Candlestick & Line chart view toggling.
  - Multi-pane synchronized crosshair cursor inspection (`x unified` spikes).
  - Integrated Volume bars with conditional up/down color formatting.
  - Interactive zoom, pan, hover inspection, and auto-fit reset.
- **Timeframe Selector**:
  - Quick period buttons: `1D`, `5D`, `1M`, `3M`, `6M`, `1Y`, `5Y`, `MAX`.
  - Automatic interval clamping respecting Yahoo Finance intraday constraints.
- **Server-Side Technical Indicators**:
  - **Trend (Overlays)**: SMA (20, 50, 100, 200), EMA (20, 50, 200).
  - **Volatility**: Bollinger Bands (20, 2 std dev) with shaded bandwidth, ATR (14).
  - **Momentum (Subplots)**: RSI (14) with 70/30 threshold boundaries, MACD (12, 26, 9) with histogram & signal lines, Stochastic Oscillator (14, 3) with 80/20 levels.
  - **Volume**: Volume Moving Average (20).
- **1-Second Real-Time Price Polling**:
  - High-speed lightweight polling endpoint (`/api/stock/{ticker}/live`) updating price, day ranges, and tick indicator.

---

## Phase 2 Features: Company Financial Statements & Fundamental Analysis

### 1. Financial Statement Normalization Layer
- **Preserved Reported Data**: Retains exact line-item names as reported by companies.
- **Standardized Line Items**: Maps common line items to uniform terminology (Total Revenue, Gross Profit, Operating Income / EBIT, Net Income / PAT, Total Assets, Total Liabilities, Total Debt, Operating Cash Flow, CapEx, Free Cash Flow).
- **Frequency Views**:
  - **Annual**: Multi-year historical statements.
  - **Quarterly**: Up to 5 recent quarterly reporting periods.
  - **TTM (Trailing Twelve Months)**: Dynamically derived by aggregating the 4 most recent quarters for flow statements (Income Statement & Cash Flow) and taking the latest quarter position for Balance Sheet.
- **Missing Data Integrity**: Missing line items remain `null` / `—` and are never assumed to be zero.

### 2. Financial Valuation, Profitability & Leverage Ratios
Each ratio discloses its exact mathematical formula and description:
- **Price to Earnings (P/E)**: `Current Share Price / Trailing 12-Month EPS`
- **Price to Book (P/B)**: `Current Share Price / Book Value Per Share`
- **Operating Margin**: `(Operating Income / Total Revenue) * 100`
- **Net Profit Margin**: `(Net Income / Total Revenue) * 100`
- **Return on Equity (ROE)**: `(Net Income / Average Shareholders' Equity) * 100`
- **Return on Assets (ROA)**: `(Net Income / Average Total Assets) * 100`
- **Current Ratio**: `Total Current Assets / Total Current Liabilities`
- **Debt to Equity**: `Total Debt / Total Shareholders' Equity`
- **Asset Turnover**: `Total Revenue / Average Total Assets`
- **CFO / PAT**: `Operating Cash Flow / Net Income (PAT)` (Earnings quality metric)
- **Free Cash Flow (FCF)**: `Operating Cash Flow - Capital Expenditure`

### 3. Growth Analysis Engine
- **Year-on-Year (YoY) Growth**: For Total Revenue and Net Profit (PAT).
- **3-Year & 5-Year CAGR**: Compounded annual growth rates calculated when sufficient observation points exist.
- **Base Period Protection**: If the base period is $\le 0$, CAGR is marked undefined (`N/A`) with an explanatory note rather than calculating misleading values.

### 4. Interactive Frontend Financials UI
- **Metadata Header**: Company name, ticker, reporting currency, and latest period.
- **Frequency Pills**: Instant toggle between `Annual`, `Quarterly`, and `TTM`.
- **Statement Tabs**: Seamless switching between `Income Statement`, `Balance Sheet`, `Cash Flow`, `Financial Ratios`, and `Growth Analysis`.
- **Plotly Trend Charts**:
  - Revenue vs Net Profit (PAT) visual comparison bar chart.
  - Operating Cash Flow (CFO) vs Free Cash Flow (FCF) visual comparison bar chart.
- **Currency & Unit Awareness**:
  - Indian equities (`INR`) format statement values in **₹ Crores** (1 Cr = 10,000,000).
  - Global equities (`USD`, `EUR`, etc.) format statement values in **Millions/Billions**.
  - Negative values styled with accounting parentheses e.g. `(1,234.50)`.
  - Horizontal scroll container with frozen first column for mobile/tablet responsiveness.

---

## API Endpoints

### Phase 1: Stock & Historical Data
- `GET /api/stock/{ticker}` — Real-time price quote and market metrics.
- `GET /api/stock/{ticker}/live` — Lightweight 1-second interval price tick endpoint.
- `GET /api/history/{ticker}?period={p}&interval={i}&indicators={ind}` — Historical OHLCV chart bars and technical indicators.
- `GET /api/search?q={query}` — Symbol and company search autocomplete.
- `GET /api/indicators/available` — Metadata for supported indicators.

### Phase 2: Financial Statements & Fundamentals
- `GET /api/financials/{ticker}/income-statement?frequency={annual|quarterly|ttm}`
- `GET /api/financials/{ticker}/balance-sheet?frequency={annual|quarterly|ttm}`
- `GET /api/financials/{ticker}/cash-flow?frequency={annual|quarterly|ttm}`
- `GET /api/financials/{ticker}/ratios`
- `GET /api/financials/{ticker}/growth`

---

## Quickstart Guide

### 1. Install Dependencies

```bash
py -3.13 -m pip install -r backend/requirements.txt
```

### 2. Run Tests

Execute unit and integration tests covering normalization, ratio formulas, CAGR calculations, and real market tickers:

```bash
py -3.13 -m unittest tests/test_financials.py -v
```

### 3. Start the Web Server

```bash
py -3.13 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Open in Browser

Open:
```text
http://localhost:8000
```

---

## Verification & Acceptance

The application has been verified against:
- **`RELIANCE.NS`** (NSE / INR, multi-segment Indian corporate, ₹ Crores formatting)
- **`TCS.NS`** (NSE / INR, Indian IT benchmark)
- **`AAPL`** (NASDAQ / USD, Global benchmark)
