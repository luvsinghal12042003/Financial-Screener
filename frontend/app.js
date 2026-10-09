/**
 * Equity Finance Screener - Modern Financial Terminal Frontend
 * Phase 1: Interactive Market Charting & Live Polling
 * Phase 2: Company Financial Statements & Fundamental Analysis
 */

// ==========================================================================
// Application State
// ==========================================================================
const state = {
    ticker: "RELIANCE.NS",
    companyName: "Reliance Industries Limited",
    currency: "INR",
    exchange: "NSE",
    period: "1y",
    interval: "1d",
    chartType: "candlestick", // 'candlestick' or 'line'
    activeIndicators: new Set(), // Set of indicator IDs: 'SMA_20', 'RSI', etc.
    quoteData: null,
    historyData: null,
    indicatorsData: {},
    isLoading: false,
    isLivePollingActive: true, // 1-second auto-fetch active
    livePollTimer: null,
    isLivePollInFlight: false,
    lastPrice: null,

    // Phase 2: Fundamental Analysis State
    activeTab: "chart", // 'chart', 'income', 'balance', 'cashflow', 'ratios', 'growth'
    financialsFrequency: "annual", // 'annual', 'quarterly', 'ttm'
    financialsCache: {}, // cache for statements, ratios, growth
    isFinancialsLoading: false,
};

// ==========================================================================
// Technical Indicator Visual Configuration
// ==========================================================================
const INDICATOR_CONFIG = {
    SMA_20: { name: "SMA 20", color: "#3b82f6", panel: "price", type: "overlay" },
    SMA_50: { name: "SMA 50", color: "#f59e0b", panel: "price", type: "overlay" },
    SMA_100: { name: "SMA 100", color: "#8b5cf6", panel: "price", type: "overlay" },
    SMA_200: { name: "SMA 200", color: "#ec4899", panel: "price", type: "overlay" },
    EMA_20: { name: "EMA 20", color: "#06b6d4", panel: "price", type: "overlay" },
    EMA_50: { name: "EMA 50", color: "#10b981", panel: "price", type: "overlay" },
    EMA_200: { name: "EMA 200", color: "#f97316", panel: "price", type: "overlay" },
    BB: { name: "Bollinger Bands", color: "#6366f1", panel: "price", type: "overlay" },
    RSI: { name: "RSI (14)", color: "#a855f7", panel: "rsi", type: "subplot" },
    MACD: { name: "MACD (12, 26, 9)", color: "#38bdf8", panel: "macd", type: "subplot" },
    STOCH: { name: "Stochastic (14, 3)", color: "#38bdf8", panel: "stoch", type: "subplot" },
    ATR: { name: "ATR (14)", color: "#fbbf24", panel: "atr", type: "subplot" },
    VOL_MA: { name: "Volume MA (20)", color: "#94a3b8", panel: "volume", type: "volume_overlay" },
};

// Major statement line items to highlight in table
const MAJOR_LINE_ITEMS = new Set([
    "Total Revenue", "Operating Revenue", "Gross Profit", "Operating Income", "EBIT", "Operating Profit",
    "Net Income", "Net Income Common Stockholders", "Net Profit",
    "Total Assets", "Total Liabilities Net Minority Interest", "Total Liabilities",
    "Stockholders Equity", "Total Equity Gross Minority Interest", "Working Capital",
    "Total Debt", "Cash And Cash Equivalents",
    "Operating Cash Flow", "Investing Cash Flow", "Financing Cash Flow", "Free Cash Flow", "Capital Expenditure"
]);

// ==========================================================================
// Formatting Helpers
// ==========================================================================
function getCurrencySymbol(curr) {
    if (!curr) return "$";
    const c = curr.toUpperCase();
    if (c === "INR") return "₹";
    if (c === "USD") return "$";
    if (c === "EUR") return "€";
    if (c === "GBP") return "£";
    if (c === "JPY") return "¥";
    return curr + " ";
}

function formatNumber(num, decimals = 2) {
    if (num === null || num === undefined || isNaN(num)) return "N/A";
    return Number(num).toLocaleString(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    });
}

function formatLargeNumber(num, currencySymbol = "") {
    if (num === null || num === undefined || isNaN(num)) return "N/A";
    const n = Number(num);
    if (n >= 1e12) return `${currencySymbol}${(n / 1e12).toFixed(2)}T`;
    if (n >= 1e9) return `${currencySymbol}${(n / 1e9).toFixed(2)}B`;
    if (n >= 1e7 && currencySymbol === "₹") return `${currencySymbol}${(n / 1e7).toFixed(2)} Cr`;
    if (n >= 1e6) return `${currencySymbol}${(n / 1e6).toFixed(2)}M`;
    if (n >= 1e3) return `${currencySymbol}${(n / 1e3).toFixed(2)}K`;
    return `${currencySymbol}${formatNumber(n)}`;
}

function formatFinancialVal(val, currency = "INR") {
    if (val === null || val === undefined || isNaN(val)) {
        return `<span class="val-empty">—</span>`;
    }
    const n = Number(val);
    const isINR = currency && currency.toUpperCase() === "INR";
    const divisor = isINR ? 1e7 : 1e6;
    const scaled = n / divisor;

    if (scaled < 0) {
        return `<span class="val-negative">(${formatNumber(Math.abs(scaled), 2)})</span>`;
    }
    return formatNumber(scaled, 2);
}

function formatRatioValue(ratio, currency = "INR") {
    if (ratio.value === null || ratio.value === undefined || isNaN(ratio.value)) {
        return "N/A";
    }
    const val = Number(ratio.value);
    if (ratio.unit === "%") {
        return `${formatNumber(val, 2)}%`;
    }
    if (ratio.unit === "x") {
        return `${formatNumber(val, 2)}x`;
    }
    if (ratio.unit === "ratio") {
        return formatNumber(val, 2);
    }
    const currSym = getCurrencySymbol(ratio.unit || currency);
    return formatLargeNumber(val, currSym);
}

function formatGrowthVal(val) {
    if (val === null || val === undefined || isNaN(val)) {
        return `<span class="growth-stat-val na">N/A</span>`;
    }
    const num = Number(val);
    const cls = num > 0 ? "positive" : num < 0 ? "negative" : "";
    const sign = num > 0 ? "+" : "";
    return `<span class="growth-stat-val ${cls}">${sign}${formatNumber(num, 2)}%</span>`;
}

// ==========================================================================
// DOM Elements
// ==========================================================================
// Search Elements
const searchForm = document.getElementById("search-form");
const searchInput = document.getElementById("ticker-search-input");
const clearSearchBtn = document.getElementById("clear-search-btn");
const searchSubmitBtn = document.getElementById("search-submit-btn");
const searchDropdown = document.getElementById("search-dropdown");
const dropdownResults = document.getElementById("dropdown-results");

// Alert Banner Elements
const alertBanner = document.getElementById("alert-banner");
const alertMessage = document.getElementById("alert-message");
const alertSuggestions = document.getElementById("alert-suggestions");
const alertCloseBtn = document.getElementById("alert-close-btn");

// Stock Header Elements
const stockCompanyName = document.getElementById("stock-company-name");
const stockTickerBadge = document.getElementById("stock-ticker-badge");
const stockExchange = document.getElementById("stock-exchange");
const stockCurrency = document.getElementById("stock-currency");
const stockPrice = document.getElementById("stock-price");
const stockChangeContainer = document.getElementById("stock-change-container");
const stockChangeArrow = document.getElementById("stock-change-arrow");
const stockChangeVal = document.getElementById("stock-change-val");
const stockChangePct = document.getElementById("stock-change-pct");

// Metric Grid Elements
const metricPrevClose = document.getElementById("metric-prev-close");
const metricDayRange = document.getElementById("metric-day-range");
const metric52wRange = document.getElementById("metric-52w-range");
const metricVolume = document.getElementById("metric-volume");
const metricMarketCap = document.getElementById("metric-market-cap");
const metricPE = document.getElementById("metric-pe");

// Live Polling Elements
const liveToggleBtn = document.getElementById("live-toggle-btn");
const livePillText = document.getElementById("live-pill-text");
const liveTickIndicator = document.getElementById("live-tick-indicator");

// Master Navigation & Workspace Views
const masterNavCard = document.getElementById("master-nav-card");
const masterTabsGroup = document.getElementById("master-tabs");
const viewChart = document.getElementById("view-chart");
const viewStatements = document.getElementById("view-statements");
const viewRatios = document.getElementById("view-ratios");
const viewGrowth = document.getElementById("view-growth");

// Global Financials Loader & Error
const financialsLoader = document.getElementById("financials-loader");
const financialsLoaderText = document.getElementById("financials-loader-text");
const financialsError = document.getElementById("financials-error");
const finErrTitle = document.getElementById("fin-err-title");
const finErrDesc = document.getElementById("fin-err-desc");

// Chart Workspace Controls
const chartLoader = document.getElementById("chart-loader");
const periodButtons = document.querySelectorAll(".period-btn");
const toggleCandlestick = document.getElementById("toggle-candlestick");
const toggleLine = document.getElementById("toggle-line");
const indicatorDropdownBtn = document.getElementById("indicator-dropdown-btn");
const indicatorMenu = document.getElementById("indicator-menu");
const closeIndMenuBtn = document.getElementById("close-ind-menu");
const activeChipsContainer = document.getElementById("active-chips-container");
const clearAllIndicatorsBtn = document.getElementById("clear-all-indicators-btn");

// Statements Workspace Elements
const statementTitleDisplay = document.getElementById("statement-title-display");
const finCompanyTag = document.getElementById("fin-company-tag");
const finCurrencyDisplay = document.getElementById("fin-currency-display");
const finLatestPeriodVal = document.getElementById("fin-latest-period-val");
const finUnitBadge = document.getElementById("fin-unit-badge");
const frequencyPillsGroup = document.getElementById("frequency-pills");

// Contextual Chart Elements
const contextualChartBox = document.getElementById("contextual-chart-box");
const contextualChartTitle = document.getElementById("contextual-chart-title");
const contextualChartSub = document.getElementById("contextual-chart-sub");
const contextualFinChart = document.getElementById("contextual-fin-chart");

// Statement Table Elements
const statementTableWrapper = document.getElementById("statement-table-wrapper");
const statementTableHead = document.getElementById("statement-table-head");
const statementTableBody = document.getElementById("statement-table-body");

// Ratios Elements
const ratiosAsOfBadge = document.getElementById("ratios-as-of-badge");
const ratiosGridValuation = document.getElementById("ratios-grid-valuation");
const ratiosGridProfitability = document.getElementById("ratios-grid-profitability");
const ratiosGridLiquidityLeverage = document.getElementById("ratios-grid-liquidity-leverage");
const ratiosGridEfficiency = document.getElementById("ratios-grid-efficiency");

// Growth Elements
const growthCardsGrid = document.getElementById("growth-cards-grid");

// ==========================================================================
// Notifications & Alerts
// ==========================================================================
function showAlert(message, suggestions = []) {
    if (!alertBanner || !alertMessage) return;
    alertMessage.textContent = message;
    if (alertSuggestions) alertSuggestions.innerHTML = "";

    if (suggestions && suggestions.length > 0 && alertSuggestions) {
        const span = document.createElement("span");
        span.textContent = "Suggestions: ";
        span.style.color = "#94a3b8";
        span.style.fontSize = "0.75rem";
        alertSuggestions.appendChild(span);

        suggestions.forEach(sym => {
            const btn = document.createElement("button");
            btn.className = "suggest-btn";
            btn.textContent = sym;
            btn.addEventListener("click", () => {
                hideAlert();
                if (searchInput) searchInput.value = sym;
                loadStock(sym);
            });
            alertSuggestions.appendChild(btn);
        });
    }

    alertBanner.style.display = "flex";
}

function hideAlert() {
    if (alertBanner) alertBanner.style.display = "none";
}

function showFinancialsError(title, message) {
    if (financialsError) {
        if (finErrTitle) finErrTitle.textContent = title;
        if (finErrDesc) finErrDesc.textContent = message;
        financialsError.style.display = "flex";
    }
}

// ==========================================================================
// Header & Metrics Rendering
// ==========================================================================
function renderStockHeader(quote) {
    if (!quote) return;

    const sym = getCurrencySymbol(quote.currency);

    if (stockCompanyName) stockCompanyName.textContent = (quote.company_name || quote.ticker).toUpperCase();
    if (stockTickerBadge) stockTickerBadge.textContent = quote.ticker;
    if (stockExchange) stockExchange.textContent = quote.exchange || "NSE";
    if (stockCurrency) stockCurrency.textContent = quote.currency || "INR";

    if (stockPrice) stockPrice.textContent = `${sym}${formatNumber(quote.price)}`;

    const isPositive = quote.change >= 0;
    if (stockChangeContainer) {
        stockChangeContainer.className = `price-change-pill ${isPositive ? "positive" : "negative"}`;
    }
    if (stockChangeArrow) stockChangeArrow.textContent = isPositive ? "▲" : "▼";
    const sign = isPositive ? "+" : "";
    if (stockChangeVal) stockChangeVal.textContent = `${sign}${sym}${formatNumber(Math.abs(quote.change))}`;
    if (stockChangePct) stockChangePct.textContent = `(${sign}${formatNumber(quote.change_percent)}%)`;

    if (metricPrevClose) {
        metricPrevClose.textContent = quote.previous_close !== null ? `${sym}${formatNumber(quote.previous_close)}` : "N/A";
    }

    // Day Range
    if (metricDayRange) {
        if (quote.day_low !== null && quote.day_high !== null) {
            metricDayRange.textContent = `${sym}${formatNumber(quote.day_low)} - ${sym}${formatNumber(quote.day_high)}`;
        } else {
            metricDayRange.textContent = "N/A";
        }
    }

    // 52 Week Range
    if (metric52wRange) {
        if (quote.fifty_two_week_low !== null && quote.fifty_two_week_high !== null) {
            metric52wRange.textContent = `${sym}${formatNumber(quote.fifty_two_week_low)} - ${sym}${formatNumber(quote.fifty_two_week_high)}`;
        } else {
            metric52wRange.textContent = "N/A";
        }
    }

    if (metricVolume) metricVolume.textContent = quote.volume ? Number(quote.volume).toLocaleString() : "N/A";
    if (metricMarketCap) metricMarketCap.textContent = formatLargeNumber(quote.market_cap, sym);
    if (metricPE) metricPE.textContent = quote.pe_ratio !== null ? formatNumber(quote.pe_ratio, 1) : "N/A";
}

// ==========================================================================
// Chart Rendering via Plotly.js (Phase 1)
// ==========================================================================
function renderChart() {
    if (!state.historyData || !state.historyData.data || state.historyData.data.length === 0) {
        return;
    }

    const dataPoints = state.historyData.data;
    const dates = dataPoints.map(d => d.date);
    const opens = dataPoints.map(d => d.open);
    const highs = dataPoints.map(d => d.high);
    const lows = dataPoints.map(d => d.low);
    const closes = dataPoints.map(d => d.close);
    const volumes = dataPoints.map(d => d.volume);

    // Active subplots
    const activeSubplots = [];
    if (state.activeIndicators.has("RSI")) activeSubplots.push("rsi");
    if (state.activeIndicators.has("MACD")) activeSubplots.push("macd");
    if (state.activeIndicators.has("STOCH")) activeSubplots.push("stoch");
    if (state.activeIndicators.has("ATR")) activeSubplots.push("atr");

    // Panels order
    const panelOrder = ["price", "volume", ...activeSubplots];
    const totalPanels = panelOrder.length;

    const weights = {
        price: 3.2,
        volume: 1.0,
        rsi: 1.25,
        macd: 1.35,
        stoch: 1.25,
        atr: 1.2,
    };

    let totalWeight = 0;
    panelOrder.forEach(p => (totalWeight += weights[p] || 1.0));

    const gap = 0.035;
    const totalGaps = (totalPanels - 1) * gap;
    const availableSpace = Math.max(0.2, 1.0 - totalGaps);

    const panelDomains = {};
    let currentY = 0.0;
    const reversedPanels = [...panelOrder].reverse();

    reversedPanels.forEach(p => {
        const h = (weights[p] / totalWeight) * availableSpace;
        panelDomains[p] = [Math.max(0, currentY), Math.min(1.0, currentY + h)];
        currentY += h + gap;
    });

    const axisMap = {
        price: "y",
        volume: "y2",
    };
    let nextAxisIdx = 3;
    activeSubplots.forEach(p => {
        axisMap[p] = `y${nextAxisIdx}`;
        nextAxisIdx++;
    });

    const traces = [];

    // 1. Price Trace (Candlestick or Line)
    if (state.chartType === "candlestick") {
        traces.push({
            type: "candlestick",
            x: dates,
            open: opens,
            high: highs,
            low: lows,
            close: closes,
            name: state.ticker,
            yaxis: axisMap.price,
            increasing: {
                line: { color: "#089981", width: 1.5 },
                fillcolor: "#089981",
            },
            decreasing: {
                line: { color: "#f23645", width: 1.5 },
                fillcolor: "#f23645",
            },
            hoverlabel: {
                bgcolor: "#1a2234",
                bordercolor: "#3b82f6",
                font: { family: "'JetBrains Mono', monospace", size: 12 },
            },
        });
    } else {
        traces.push({
            type: "scatter",
            mode: "lines",
            x: dates,
            y: closes,
            name: `${state.ticker} Price`,
            yaxis: axisMap.price,
            line: { color: "#38bdf8", width: 2 },
            hoverlabel: {
                bgcolor: "#1a2234",
                bordercolor: "#38bdf8",
                font: { family: "'JetBrains Mono', monospace", size: 12 },
            },
        });
    }

    // 2. Trend & Volatility Overlays on Price Panel
    const indicators = state.indicatorsData || {};

    // SMA / EMA Overlays
    ["SMA_20", "SMA_50", "SMA_100", "SMA_200", "EMA_20", "EMA_50", "EMA_200"].forEach(id => {
        if (state.activeIndicators.has(id) && indicators[id]) {
            const cfg = INDICATOR_CONFIG[id];
            traces.push({
                type: "scatter",
                mode: "lines",
                x: dates,
                y: indicators[id],
                name: cfg.name,
                yaxis: axisMap.price,
                line: { color: cfg.color, width: 1.6 },
                hoverlabel: {
                    bgcolor: "#1a2234",
                    font: { family: "'JetBrains Mono', monospace", size: 11 },
                },
            });
        }
    });

    // Bollinger Bands Overlay
    if (state.activeIndicators.has("BB") && indicators.BB) {
        const bb = indicators.BB;
        traces.push({
            type: "scatter",
            mode: "lines",
            x: dates,
            y: bb.upper,
            name: "BB Upper (20, 2)",
            yaxis: axisMap.price,
            line: { color: "rgba(99, 102, 241, 0.75)", width: 1.2, dash: "dot" },
            showlegend: true,
        });
        traces.push({
            type: "scatter",
            mode: "lines",
            x: dates,
            y: bb.middle,
            name: "BB Middle (SMA 20)",
            yaxis: axisMap.price,
            line: { color: "#6366f1", width: 1.4 },
            showlegend: false,
        });
        traces.push({
            type: "scatter",
            mode: "lines",
            x: dates,
            y: bb.lower,
            name: "BB Lower",
            yaxis: axisMap.price,
            line: { color: "rgba(99, 102, 241, 0.75)", width: 1.2, dash: "dot" },
            fill: "tonexty",
            fillcolor: "rgba(99, 102, 241, 0.08)",
            showlegend: false,
        });
    }

    // 3. Volume Panel
    const volumeColors = dataPoints.map(d => (d.close >= d.open ? "rgba(8, 153, 129, 0.65)" : "rgba(242, 54, 69, 0.65)"));
    traces.push({
        type: "bar",
        x: dates,
        y: volumes,
        name: "Volume",
        yaxis: axisMap.volume,
        marker: { color: volumeColors },
        hoverlabel: {
            bgcolor: "#1a2234",
            font: { family: "'JetBrains Mono', monospace", size: 11 },
        },
    });

    if (state.activeIndicators.has("VOL_MA") && indicators.VOL_MA) {
        traces.push({
            type: "scatter",
            mode: "lines",
            x: dates,
            y: indicators.VOL_MA,
            name: "Vol MA (20)",
            yaxis: axisMap.volume,
            line: { color: "#cbd5e1", width: 1.5 },
        });
    }

    // 4. RSI Subplot
    if (state.activeIndicators.has("RSI") && indicators.RSI) {
        const rsiAxis = axisMap.rsi;
        traces.push({
            type: "scatter",
            mode: "lines",
            x: dates,
            y: indicators.RSI,
            name: "RSI (14)",
            yaxis: rsiAxis,
            line: { color: "#a855f7", width: 2 },
        });
        traces.push({
            type: "scatter",
            mode: "lines",
            x: dates,
            y: Array(dates.length).fill(70),
            name: "RSI 70 (Overbought)",
            yaxis: rsiAxis,
            line: { color: "rgba(242, 54, 69, 0.5)", width: 1, dash: "dash" },
            hoverinfo: "skip",
            showlegend: false,
        });
        traces.push({
            type: "scatter",
            mode: "lines",
            x: dates,
            y: Array(dates.length).fill(30),
            name: "RSI 30 (Oversold)",
            yaxis: rsiAxis,
            line: { color: "rgba(8, 153, 129, 0.5)", width: 1, dash: "dash" },
            hoverinfo: "skip",
            showlegend: false,
        });
    }

    // 5. MACD Subplot
    if (state.activeIndicators.has("MACD") && indicators.MACD) {
        const macdData = indicators.MACD;
        const macdAxis = axisMap.macd;
        const histColors = (macdData.histogram || []).map(v => (v >= 0 ? "rgba(8, 153, 129, 0.7)" : "rgba(242, 54, 69, 0.7)"));
        traces.push({
            type: "bar",
            x: dates,
            y: macdData.histogram,
            name: "MACD Hist",
            yaxis: macdAxis,
            marker: { color: histColors },
        });
        traces.push({
            type: "scatter",
            mode: "lines",
            x: dates,
            y: macdData.macd,
            name: "MACD (12, 26)",
            yaxis: macdAxis,
            line: { color: "#38bdf8", width: 1.8 },
        });
        traces.push({
            type: "scatter",
            mode: "lines",
            x: dates,
            y: macdData.signal,
            name: "Signal (9)",
            yaxis: macdAxis,
            line: { color: "#f43f5e", width: 1.6 },
        });
    }

    // 6. Stochastic Subplot
    if (state.activeIndicators.has("STOCH") && indicators.STOCH) {
        const stochAxis = axisMap.stoch;
        traces.push({
            type: "scatter",
            mode: "lines",
            x: dates,
            y: indicators.STOCH.k,
            name: "%K (14)",
            yaxis: stochAxis,
            line: { color: "#38bdf8", width: 1.8 },
        });
        traces.push({
            type: "scatter",
            mode: "lines",
            x: dates,
            y: indicators.STOCH.d,
            name: "%D (3)",
            yaxis: stochAxis,
            line: { color: "#f59e0b", width: 1.6 },
        });
        traces.push({
            type: "scatter",
            mode: "lines",
            x: dates,
            y: Array(dates.length).fill(80),
            yaxis: stochAxis,
            line: { color: "rgba(255, 255, 255, 0.2)", width: 1, dash: "dot" },
            hoverinfo: "skip",
            showlegend: false,
        });
        traces.push({
            type: "scatter",
            mode: "lines",
            x: dates,
            y: Array(dates.length).fill(20),
            yaxis: stochAxis,
            line: { color: "rgba(255, 255, 255, 0.2)", width: 1, dash: "dot" },
            hoverinfo: "skip",
            showlegend: false,
        });
    }

    // 7. ATR Subplot
    if (state.activeIndicators.has("ATR") && indicators.ATR) {
        const atrAxis = axisMap.atr;
        traces.push({
            type: "scatter",
            mode: "lines",
            x: dates,
            y: indicators.ATR,
            name: "ATR (14)",
            yaxis: atrAxis,
            line: { color: "#fbbf24", width: 1.8 },
        });
    }

    // Container height calculation
    const containerHeight = Math.max(580, 520 + activeSubplots.length * 150);
    const canvasContainer = document.getElementById("chart-canvas-container");
    const plotlyContainer = document.getElementById("plotly-chart");
    if (canvasContainer) canvasContainer.style.minHeight = `${containerHeight}px`;
    if (plotlyContainer) plotlyContainer.style.minHeight = `${containerHeight}px`;

    const layout = {
        autosize: true,
        height: containerHeight,
        margin: { l: 20, r: 65, t: 30, b: 40 },
        paper_bgcolor: "#121824",
        plot_bgcolor: "#0b0f17",
        showlegend: true,
        legend: {
            orientation: "h",
            x: 0,
            y: 1.05,
            xanchor: "left",
            font: { family: "'Plus Jakarta Sans', sans-serif", size: 11, color: "#94a3b8" },
            bgcolor: "rgba(18, 24, 36, 0.8)",
        },
        hovermode: "x unified",
        xaxis: {
            domain: [0, 1],
            rangeslider: { visible: false },
            showgrid: true,
            gridcolor: "rgba(255, 255, 255, 0.05)",
            spikemode: "across",
            spikesnap: "cursor",
            spikedash: "dash",
            spikethickness: 1,
            spikecolor: "rgba(255, 255, 255, 0.3)",
            tickfont: { family: "'JetBrains Mono', monospace", size: 11, color: "#94a3b8" },
        },
        yaxis: {
            domain: panelDomains.price,
            showgrid: true,
            gridcolor: "rgba(255, 255, 255, 0.05)",
            side: "right",
            tickfont: { family: "'JetBrains Mono', monospace", size: 11, color: "#94a3b8" },
            spikemode: "across",
            spikesnap: "cursor",
            spikedash: "dash",
            spikethickness: 1,
            spikecolor: "rgba(255, 255, 255, 0.25)",
        },
        yaxis2: {
            domain: panelDomains.volume,
            showgrid: true,
            gridcolor: "rgba(255, 255, 255, 0.04)",
            side: "right",
            showticklabels: true,
            tickfont: { family: "'JetBrains Mono', monospace", size: 10, color: "#64748b" },
            title: { text: "Vol", font: { size: 10, color: "#64748b" } },
        },
    };

    if (axisMap.rsi) {
        layout[axisMap.rsi.replace("y", "yaxis")] = {
            domain: panelDomains.rsi,
            showgrid: true,
            gridcolor: "rgba(255, 255, 255, 0.04)",
            side: "right",
            range: [0, 100],
            tickvals: [30, 70],
            tickfont: { family: "'JetBrains Mono', monospace", size: 10, color: "#94a3b8" },
            title: { text: "RSI", font: { size: 11, color: "#a855f7" } },
        };
    }

    if (axisMap.macd) {
        layout[axisMap.macd.replace("y", "yaxis")] = {
            domain: panelDomains.macd,
            showgrid: true,
            gridcolor: "rgba(255, 255, 255, 0.04)",
            side: "right",
            tickfont: { family: "'JetBrains Mono', monospace", size: 10, color: "#94a3b8" },
            title: { text: "MACD", font: { size: 11, color: "#38bdf8" } },
        };
    }

    if (axisMap.stoch) {
        layout[axisMap.stoch.replace("y", "yaxis")] = {
            domain: panelDomains.stoch,
            showgrid: true,
            gridcolor: "rgba(255, 255, 255, 0.04)",
            side: "right",
            range: [0, 100],
            tickvals: [20, 80],
            tickfont: { family: "'JetBrains Mono', monospace", size: 10, color: "#94a3b8" },
            title: { text: "Stoch", font: { size: 11, color: "#38bdf8" } },
        };
    }

    if (axisMap.atr) {
        layout[axisMap.atr.replace("y", "yaxis")] = {
            domain: panelDomains.atr,
            showgrid: true,
            gridcolor: "rgba(255, 255, 255, 0.04)",
            side: "right",
            tickfont: { family: "'JetBrains Mono', monospace", size: 10, color: "#94a3b8" },
            title: { text: "ATR", font: { size: 11, color: "#fbbf24" } },
        };
    }

    const config = {
        responsive: true,
        displayModeBar: true,
        displaylogo: false,
        modeBarButtonsToRemove: ["lasso2d", "select2d"],
    };

    Plotly.react("plotly-chart", traces, layout, config);
}

// ==========================================================================
// Indicator Chip Management (Phase 1)
// ==========================================================================
function updateActiveIndicatorChips() {
    if (!activeChipsContainer) return;
    activeChipsContainer.innerHTML = "";

    if (state.activeIndicators.size === 0) {
        const hint = document.createElement("span");
        hint.className = "no-indicators-hint";
        hint.textContent = 'No indicators applied. Click "+ Add Indicator" above.';
        activeChipsContainer.appendChild(hint);
        if (clearAllIndicatorsBtn) clearAllIndicatorsBtn.style.display = "none";
        return;
    }

    if (clearAllIndicatorsBtn) clearAllIndicatorsBtn.style.display = "inline-block";

    state.activeIndicators.forEach(id => {
        const cfg = INDICATOR_CONFIG[id];
        if (!cfg) return;

        const chip = document.createElement("div");
        chip.className = "indicator-chip";

        const dot = document.createElement("span");
        dot.className = "chip-color-dot";
        dot.style.backgroundColor = cfg.color;

        const text = document.createElement("span");
        text.textContent = cfg.name;

        const removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.className = "chip-remove";
        removeBtn.textContent = "✕";
        removeBtn.title = `Remove ${cfg.name}`;
        removeBtn.addEventListener("click", () => {
            toggleIndicator(id, false);
        });

        chip.appendChild(dot);
        chip.appendChild(text);
        chip.appendChild(removeBtn);
        activeChipsContainer.appendChild(chip);
    });
}

function syncIndicatorCheckboxes() {
    document.querySelectorAll(".ind-option input[type='checkbox']").forEach(cb => {
        const id = cb.getAttribute("data-id");
        cb.checked = state.activeIndicators.has(id);
    });
}

async function toggleIndicator(id, enable) {
    if (enable) {
        state.activeIndicators.add(id);
    } else {
        state.activeIndicators.delete(id);
    }

    syncIndicatorCheckboxes();
    updateActiveIndicatorChips();

    if (enable && (!state.indicatorsData || !state.indicatorsData[id])) {
        await refreshIndicators();
    } else {
        renderChart();
    }
}

async function refreshIndicators() {
    if (state.activeIndicators.size === 0) {
        state.indicatorsData = {};
        renderChart();
        return;
    }

    const indList = Array.from(state.activeIndicators).join(",");
    try {
        const url = `/api/indicators/${encodeURIComponent(state.ticker)}?period=${state.period}&interval=${state.interval}&indicators=${encodeURIComponent(indList)}`;
        const resp = await fetch(url);
        if (resp.ok) {
            const data = await resp.json();
            state.indicatorsData = data.indicators || {};
            renderChart();
        }
    } catch (err) {
        console.warn("Error refreshing indicators:", err);
    }
}

// ==========================================================================
// Real-Time 1-Second Live Polling Engine
// ==========================================================================
const LIVE_POLL_INTERVAL_MS = 1000;

function startLivePolling() {
    stopLivePolling();
    if (!state.isLivePollingActive) return;

    if (liveToggleBtn) {
        liveToggleBtn.classList.remove("paused");
        liveToggleBtn.classList.add("active");
        if (livePillText) livePillText.textContent = "LIVE (1s)";
    }

    state.livePollTimer = setInterval(pollLivePrice, LIVE_POLL_INTERVAL_MS);
}

function stopLivePolling() {
    if (state.livePollTimer) {
        clearInterval(state.livePollTimer);
        state.livePollTimer = null;
    }
    if (liveToggleBtn) {
        liveToggleBtn.classList.remove("active");
        liveToggleBtn.classList.add("paused");
        if (livePillText) livePillText.textContent = "PAUSED";
    }
}

async function pollLivePrice() {
    if (!state.isLivePollingActive) return;
    if (document.hidden) return;
    if (state.isLivePollInFlight || state.isLoading) return;
    if (!state.ticker) return;

    state.isLivePollInFlight = true;
    try {
        const resp = await fetch(`/api/stock/${encodeURIComponent(state.ticker)}/live`);
        if (!resp.ok) return;

        const live = await resp.json();
        updateLivePriceUI(live);
    } catch (err) {
        console.debug("Live tick poll error:", err);
    } finally {
        state.isLivePollInFlight = false;
    }
}

function updateLivePriceUI(live) {
    if (!live || live.price === undefined || live.price === null) return;

    const sym = getCurrencySymbol(live.currency || state.currency);
    const newPrice = Number(live.price);
    const oldPrice = state.lastPrice !== null ? state.lastPrice : state.quoteData?.price;

    // Price Flash Visual Effect
    if (oldPrice !== null && oldPrice !== undefined && stockPrice) {
        if (newPrice > oldPrice) {
            stockPrice.classList.remove("price-flash-up", "price-flash-down");
            void stockPrice.offsetWidth;
            stockPrice.classList.add("price-flash-up");
        } else if (newPrice < oldPrice) {
            stockPrice.classList.remove("price-flash-up", "price-flash-down");
            void stockPrice.offsetWidth;
            stockPrice.classList.add("price-flash-down");
        }
    }
    state.lastPrice = newPrice;

    if (stockPrice) {
        stockPrice.textContent = `${sym}${formatNumber(newPrice)}`;
    }

    if (stockChangeContainer) {
        const isPositive = live.change >= 0;
        stockChangeContainer.className = `price-change-pill ${isPositive ? "positive" : "negative"}`;
        if (stockChangeArrow) stockChangeArrow.textContent = isPositive ? "▲" : "▼";
        const sign = isPositive ? "+" : "";
        if (stockChangeVal) stockChangeVal.textContent = `${sign}${sym}${formatNumber(Math.abs(live.change))}`;
        if (stockChangePct) stockChangePct.textContent = `(${sign}${formatNumber(live.change_percent)}%)`;
    }

    if (live.day_low !== null && live.day_high !== null && metricDayRange) {
        metricDayRange.textContent = `${sym}${formatNumber(live.day_low)} - ${sym}${formatNumber(live.day_high)}`;
    }

    if (live.volume !== null && metricVolume) {
        metricVolume.textContent = Number(live.volume).toLocaleString();
    }

    if (liveTickIndicator) {
        const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        liveTickIndicator.textContent = `1s tick • ${timeStr}`;
    }

    // Live update 1D candle close
    if (state.period === "1d" && state.historyData && state.historyData.data && state.historyData.data.length > 0) {
        const candles = state.historyData.data;
        const lastCandle = candles[candles.length - 1];
        if (lastCandle) {
            lastCandle.close = newPrice;
            if (newPrice > lastCandle.high) lastCandle.high = newPrice;
            if (newPrice < lastCandle.low) lastCandle.low = newPrice;
            if (live.volume) lastCandle.volume = live.volume;
        }
    }
}

// ==========================================================================
// Stock Loading & Period Management
// ==========================================================================
async function loadStock(query, period = state.period) {
    if (state.isLoading) return;

    state.isLoading = true;
    hideAlert();
    if (chartLoader) chartLoader.style.display = "flex";
    if (searchSubmitBtn) searchSubmitBtn.disabled = true;

    try {
        const quotePromise = fetch(`/api/stock/${encodeURIComponent(query)}`);
        const indParams = state.activeIndicators.size > 0 ? `&indicators=${encodeURIComponent(Array.from(state.activeIndicators).join(","))}` : "";
        const historyPromise = fetch(`/api/history/${encodeURIComponent(query)}?period=${period}${indParams}`);

        const [quoteResp, histResp] = await Promise.all([quotePromise, historyPromise]);

        if (!quoteResp.ok) {
            const errData = await quoteResp.json().catch(() => ({}));
            throw new Error(errData.detail || "Unable to find ticker.");
        }

        if (!histResp.ok) {
            const errData = await histResp.json().catch(() => ({}));
            throw new Error(errData.detail || "Historical data is unavailable.");
        }

        const quote = await quoteResp.json();
        const history = await histResp.json();

        // Update Global State
        state.ticker = quote.ticker;
        state.companyName = quote.company_name;
        state.currency = quote.currency;
        state.exchange = quote.exchange;
        state.period = period;
        state.interval = history.interval;
        state.quoteData = quote;
        state.lastPrice = quote.price;
        state.historyData = history;
        state.indicatorsData = history.indicators || {};

        // Invalidate cache for new company
        state.financialsCache = {};

        // Update UI
        if (searchInput) searchInput.value = quote.ticker;
        renderStockHeader(quote);

        // Render current active tab workspace
        if (state.activeTab === "chart") {
            renderChart();
        } else {
            switchMasterTab(state.activeTab);
        }

        // Start 1-second live polling
        startLivePolling();
    } catch (error) {
        console.error("Failed to load stock data:", error);
        showAlert(error.message, ["AAPL", "RELIANCE.NS", "TCS.NS", "INFY.NS", "MSFT"]);
    } finally {
        state.isLoading = false;
        if (chartLoader) chartLoader.style.display = "none";
        if (searchSubmitBtn) searchSubmitBtn.disabled = false;
    }
}

async function changePeriod(newPeriod) {
    if (state.period === newPeriod || state.isLoading) return;

    periodButtons.forEach(btn => {
        btn.classList.toggle("active", btn.getAttribute("data-period") === newPeriod);
    });

    state.period = newPeriod;
    await loadStock(state.ticker, newPeriod);
}

// ==========================================================================
// Search & Autocomplete
// ==========================================================================
let searchDebounceTimer = null;

async function performSearch(query) {
    if (!query || query.trim().length === 0) {
        if (searchDropdown) searchDropdown.style.display = "none";
        return;
    }

    try {
        const resp = await fetch(`/api/search?q=${encodeURIComponent(query.trim())}`);
        if (!resp.ok) return;

        const data = await resp.json();
        const results = data.results || [];

        if (results.length === 0 || !dropdownResults || !searchDropdown) {
            if (searchDropdown) searchDropdown.style.display = "none";
            return;
        }

        dropdownResults.innerHTML = "";
        results.forEach(item => {
            const row = document.createElement("div");
            row.className = "dropdown-item";

            row.innerHTML = `
                <div style="display:flex; align-items:center; flex:1; min-width:0;">
                    <span class="dropdown-symbol">${item.ticker}</span>
                    <span class="dropdown-name">${item.name}</span>
                </div>
                <div class="dropdown-badges">
                    <span class="badge-tag">${item.exchange || "US"}</span>
                </div>
            `;

            row.addEventListener("click", () => {
                searchDropdown.style.display = "none";
                if (searchInput) searchInput.value = item.ticker;
                loadStock(item.ticker);
            });

            dropdownResults.appendChild(row);
        });

        searchDropdown.style.display = "block";
    } catch (err) {
        console.warn("Search error:", err);
    }
}

// ==========================================================================
// Phase 2: Master Tab Navigation & Workspace Switching
// ==========================================================================
async function switchMasterTab(tab) {
    if (!tab) return;
    state.activeTab = tab;

    // 1. Update button states
    document.querySelectorAll(".master-tab-btn").forEach(btn => {
        btn.classList.toggle("active", btn.getAttribute("data-tab") === tab);
    });

    // 2. Hide error card
    if (financialsError) financialsError.style.display = "none";

    // 3. Switch workspace visibility
    const isStmt = tab === "income" || tab === "balance" || tab === "cashflow";

    if (viewChart) {
        viewChart.style.display = tab === "chart" ? "block" : "none";
        viewChart.classList.toggle("active", tab === "chart");
    }
    if (viewStatements) {
        viewStatements.style.display = isStmt ? "block" : "none";
        viewStatements.classList.toggle("active", isStmt);
    }
    if (viewRatios) {
        viewRatios.style.display = tab === "ratios" ? "block" : "none";
        viewRatios.classList.toggle("active", tab === "ratios");
    }
    if (viewGrowth) {
        viewGrowth.style.display = tab === "growth" ? "block" : "none";
        viewGrowth.classList.toggle("active", tab === "growth");
    }

    // 4. Load View Data
    if (tab === "chart") {
        renderChart();
        setTimeout(() => {
            try { Plotly.Plots.resize("plotly-chart"); } catch (e) {}
        }, 50);
        return;
    }

    if (isStmt) {
        updateStatementMetadata();
        await loadStatementData(tab, state.financialsFrequency);
    } else if (tab === "ratios") {
        await loadRatiosData();
    } else if (tab === "growth") {
        await loadGrowthData();
    }
}

async function switchFrequency(freq) {
    if (state.financialsFrequency === freq) return;
    state.financialsFrequency = freq;

    document.querySelectorAll(".freq-pill").forEach(pill => {
        pill.classList.toggle("active", pill.getAttribute("data-freq") === freq);
    });

    const tab = state.activeTab;
    if (tab === "income" || tab === "balance" || tab === "cashflow") {
        await loadStatementData(tab, freq);
    }
}

function updateStatementMetadata() {
    const isINR = (state.currency || "INR").toUpperCase() === "INR";
    if (finCompanyTag) {
        finCompanyTag.textContent = state.ticker;
    }
    if (finCurrencyDisplay) {
        finCurrencyDisplay.innerHTML = `Currency: <strong>${state.currency || "INR"}</strong>`;
    }
    if (finUnitBadge) {
        finUnitBadge.textContent = isINR ? "Unit: ₹ Crores" : `Unit: ${state.currency || "USD"} Millions`;
    }

    const tab = state.activeTab;
    if (statementTitleDisplay) {
        if (tab === "income") statementTitleDisplay.textContent = "Income Statement";
        else if (tab === "balance") statementTitleDisplay.textContent = "Balance Sheet";
        else if (tab === "cashflow") statementTitleDisplay.textContent = "Cash Flow Statement";
    }
}

// ==========================================================================
// Financial Statements (Income, Balance, Cash Flow) Engine
// ==========================================================================
async function loadStatementData(tab, freq = state.financialsFrequency) {
    if (!state.ticker) return;
    const ticker = state.ticker;

    const endpoint = tab === "balance" ? "balance-sheet" : (tab === "cashflow" ? "cash-flow" : "income-statement");
    const cacheKey = `stmt_${ticker}_${endpoint}_${freq}`;

    if (financialsLoader) {
        if (financialsLoaderText) {
            const title = statementTitleDisplay ? statementTitleDisplay.textContent : "statement";
            financialsLoaderText.textContent = `Loading ${title}...`;
        }
        financialsLoader.style.display = "flex";
    }
    if (financialsError) financialsError.style.display = "none";

    try {
        let data = state.financialsCache[cacheKey];
        if (!data) {
            const resp = await fetch(`/api/financials/${encodeURIComponent(ticker)}/${endpoint}?frequency=${freq}`);
            if (!resp.ok) {
                const errData = await resp.json().catch(() => ({}));
                throw new Error(errData.detail || `Unable to load ${endpoint.replace("-", " ")}.`);
            }
            data = await resp.json();
            state.financialsCache[cacheKey] = data;
        }

        if (finLatestPeriodVal) {
            finLatestPeriodVal.textContent = data.periods && data.periods.length > 0 ? data.periods[0] : "--";
        }

        renderStatementTable(data);
        renderContextualChart(tab, freq, data);
    } catch (err) {
        console.warn("Statement loading error:", err);
        showFinancialsError("Statement Unavailable", err.message);
        if (statementTableBody) {
            statementTableBody.innerHTML = `<tr><td colspan="10" style="text-align:center; padding: 2rem; color: var(--text-muted);">${err.message}</td></tr>`;
        }
        if (contextualChartBox) contextualChartBox.style.display = "none";
    } finally {
        if (financialsLoader) financialsLoader.style.display = "none";
    }
}

function isMajorLineItem(item) {
    if (!item) return false;
    const label = item.standard_label || item.name || "";
    if (MAJOR_LINE_ITEMS.has(label)) return true;
    for (const m of MAJOR_LINE_ITEMS) {
        if (label.toLowerCase() === m.toLowerCase()) return true;
    }
    return false;
}

function renderStatementTable(data) {
    if (!statementTableHead || !statementTableBody) return;

    statementTableHead.innerHTML = "";
    statementTableBody.innerHTML = "";

    const periods = data.periods || [];
    const lineItems = data.line_items || [];

    // Header Row
    const trHead = document.createElement("tr");
    const thName = document.createElement("th");
    thName.className = "col-head-name";
    thName.textContent = "Financial Line Item";
    trHead.appendChild(thName);

    periods.forEach(p => {
        const th = document.createElement("th");
        th.className = "col-head-period";
        th.textContent = p;
        trHead.appendChild(th);
    });
    statementTableHead.appendChild(trHead);

    // Body Rows
    if (lineItems.length === 0) {
        const trEmpty = document.createElement("tr");
        const tdEmpty = document.createElement("td");
        tdEmpty.colSpan = periods.length + 1;
        tdEmpty.style.textAlign = "center";
        tdEmpty.style.padding = "2.5rem";
        tdEmpty.style.color = "var(--text-muted)";
        tdEmpty.textContent = "No financial statement data available for this reporting frequency.";
        trEmpty.appendChild(tdEmpty);
        statementTableBody.appendChild(trEmpty);
        return;
    }

    lineItems.forEach(item => {
        const tr = document.createElement("tr");
        if (isMajorLineItem(item)) {
            tr.classList.add("row-major");
        }

        const tdName = document.createElement("td");
        tdName.className = "col-line-name";

        const divDisplay = document.createElement("div");
        divDisplay.className = "line-item-display";

        const spanMain = document.createElement("span");
        spanMain.className = "line-item-main";
        spanMain.textContent = item.standard_label || item.name;
        divDisplay.appendChild(spanMain);

        if (item.standard_label && item.standard_label !== item.name) {
            const spanOrig = document.createElement("span");
            spanOrig.className = "line-item-orig";
            spanOrig.textContent = `Reported: ${item.name}`;
            divDisplay.appendChild(spanOrig);
        }

        tdName.appendChild(divDisplay);
        tr.appendChild(tdName);

        periods.forEach(p => {
            const tdVal = document.createElement("td");
            tdVal.className = "col-line-val";
            const val = item.values ? item.values[p] : null;
            tdVal.innerHTML = formatFinancialVal(val, data.currency);
            tr.appendChild(tdVal);
        });

        statementTableBody.appendChild(tr);
    });
}

function renderContextualChart(tab, freq, statementData) {
    if (!contextualFinChart || !contextualChartBox) return;

    if (tab === "balance") {
        contextualChartBox.style.display = "none";
        return;
    }

    const periods = [...(statementData.periods || [])].reverse();
    if (periods.length === 0) {
        contextualChartBox.style.display = "none";
        return;
    }

    const isINR = (state.currency || "INR").toUpperCase() === "INR";
    const divisor = isINR ? 1e7 : 1e6;
    const unitLabel = isINR ? "₹ Cr" : `${state.currency || "USD"}M`;

    let traces = [];

    if (tab === "income") {
        contextualChartBox.style.display = "block";
        if (contextualChartTitle) contextualChartTitle.textContent = "Revenue & Net Profit Trend";
        if (contextualChartSub) contextualChartSub.textContent = `${freq.toUpperCase()} Trend (${unitLabel}) • ${state.companyName || state.ticker}`;

        const revItem = (statementData.line_items || []).find(i =>
            (i.standard_label && i.standard_label.toLowerCase().includes("revenue")) ||
            i.name.toLowerCase().includes("total revenue") ||
            i.name.toLowerCase().includes("operating revenue") ||
            i.name.toLowerCase().includes("revenue")
        );

        const netItem = (statementData.line_items || []).find(i =>
            (i.standard_label && i.standard_label.toLowerCase().includes("net income")) ||
            i.name.toLowerCase().includes("net income") ||
            i.name.toLowerCase().includes("net profit")
        );

        const revVals = periods.map(p => revItem && revItem.values && revItem.values[p] != null ? +(revItem.values[p] / divisor).toFixed(2) : null);
        const netVals = periods.map(p => netItem && netItem.values && netItem.values[p] != null ? +(netItem.values[p] / divisor).toFixed(2) : null);

        traces = [
            {
                x: periods,
                y: revVals,
                type: 'bar',
                name: `Revenue (${unitLabel})`,
                marker: { color: '#3b82f6', opacity: 0.85 }
            },
            {
                x: periods,
                y: netVals,
                type: 'bar',
                name: `Net Profit (${unitLabel})`,
                marker: { color: '#10b981', opacity: 0.9 }
            }
        ];
    } else if (tab === "cashflow") {
        contextualChartBox.style.display = "block";
        if (contextualChartTitle) contextualChartTitle.textContent = "Operating Cash Flow vs Free Cash Flow";
        if (contextualChartSub) contextualChartSub.textContent = `${freq.toUpperCase()} Cash Generation (${unitLabel}) • ${state.companyName || state.ticker}`;

        const cfoItem = (statementData.line_items || []).find(i =>
            (i.standard_label && i.standard_label.toLowerCase().includes("cfo")) ||
            i.name.toLowerCase().includes("operating cash flow")
        );

        const fcfItem = (statementData.line_items || []).find(i =>
            (i.standard_label && i.standard_label.toLowerCase().includes("fcf")) ||
            i.name.toLowerCase().includes("free cash flow")
        );

        const cfoVals = periods.map(p => cfoItem && cfoItem.values && cfoItem.values[p] != null ? +(cfoItem.values[p] / divisor).toFixed(2) : null);
        const fcfVals = periods.map(p => fcfItem && fcfItem.values && fcfItem.values[p] != null ? +(fcfItem.values[p] / divisor).toFixed(2) : null);

        traces = [
            {
                x: periods,
                y: cfoVals,
                type: 'bar',
                name: `Operating CF (${unitLabel})`,
                marker: { color: '#06b6d4', opacity: 0.85 }
            },
            {
                x: periods,
                y: fcfVals,
                type: 'bar',
                name: `Free Cash Flow (${unitLabel})`,
                marker: { color: '#a855f7', opacity: 0.9 }
            }
        ];
    }

    const layout = {
        barmode: 'group',
        paper_bgcolor: '#161e2e',
        plot_bgcolor: '#121824',
        font: { family: "'Plus Jakarta Sans', sans-serif", color: '#94a3b8', size: 11 },
        margin: { t: 20, r: 20, l: 55, b: 35 },
        height: 230,
        legend: { orientation: 'h', x: 0, y: 1.15, font: { size: 10 } },
        xaxis: { gridcolor: 'rgba(255, 255, 255, 0.05)', linecolor: 'rgba(255, 255, 255, 0.1)', tickfont: { family: "'JetBrains Mono', monospace", size: 10 } },
        yaxis: { gridcolor: 'rgba(255, 255, 255, 0.05)', linecolor: 'rgba(255, 255, 255, 0.1)', tickfont: { family: "'JetBrains Mono', monospace", size: 10 } }
    };

    Plotly.react(contextualFinChart, traces, layout, { responsive: true, displayModeBar: false });
}

// ==========================================================================
// Financial Ratios Engine
// ==========================================================================
async function loadRatiosData() {
    if (!state.ticker) return;
    const ticker = state.ticker;
    const cacheKey = `ratios_${ticker}`;

    if (financialsLoader) {
        if (financialsLoaderText) financialsLoaderText.textContent = "Computing valuation multiples and fundamental ratios...";
        financialsLoader.style.display = "flex";
    }
    if (financialsError) financialsError.style.display = "none";

    try {
        let data = state.financialsCache[cacheKey];
        if (!data) {
            const resp = await fetch(`/api/financials/${encodeURIComponent(ticker)}/ratios`);
            if (!resp.ok) {
                const errData = await resp.json().catch(() => ({}));
                throw new Error(errData.detail || "Unable to compute financial ratios.");
            }
            data = await resp.json();
            state.financialsCache[cacheKey] = data;
        }

        if (ratiosAsOfBadge) {
            ratiosAsOfBadge.textContent = data.as_of_date ? `As of: ${data.as_of_date}` : "Latest Filing";
        }
        renderRatiosView(data);
    } catch (err) {
        console.warn("Ratios loading error:", err);
        showFinancialsError("Financial Ratios Unavailable", err.message);
    } finally {
        if (financialsLoader) financialsLoader.style.display = "none";
    }
}

function renderRatiosView(data) {
    if (!ratiosGridValuation || !ratiosGridProfitability || !ratiosGridLiquidityLeverage || !ratiosGridEfficiency) return;

    ratiosGridValuation.innerHTML = "";
    ratiosGridProfitability.innerHTML = "";
    ratiosGridLiquidityLeverage.innerHTML = "";
    ratiosGridEfficiency.innerHTML = "";

    const ratios = data.ratios || [];

    ratios.forEach(r => {
        const card = document.createElement("div");
        card.className = "ratio-card";

        const topRow = document.createElement("div");
        topRow.className = "ratio-card-top";

        const title = document.createElement("span");
        title.className = "ratio-card-title";
        title.textContent = r.name;

        const catPill = document.createElement("span");
        catPill.className = "ratio-category-pill";
        catPill.textContent = r.category;

        topRow.appendChild(title);
        topRow.appendChild(catPill);
        card.appendChild(topRow);

        const valRow = document.createElement("div");
        valRow.className = "ratio-card-val-row";

        const valSpan = document.createElement("span");
        valSpan.className = "ratio-val-large";
        valSpan.textContent = formatRatioValue(r, data.currency);
        valRow.appendChild(valSpan);
        card.appendChild(valRow);

        if (r.formula) {
            const formulaBox = document.createElement("div");
            formulaBox.className = "ratio-formula-container";
            formulaBox.title = `Formula: ${r.formula}`;
            formulaBox.textContent = `Formula: ${r.formula}`;
            card.appendChild(formulaBox);
        }

        if (r.description) {
            const desc = document.createElement("div");
            desc.className = "ratio-description-text";
            desc.textContent = r.description;
            card.appendChild(desc);
        }

        if (r.category === "valuation") {
            ratiosGridValuation.appendChild(card);
        } else if (r.category === "profitability") {
            ratiosGridProfitability.appendChild(card);
        } else if (r.category === "liquidity" || r.category === "leverage") {
            ratiosGridLiquidityLeverage.appendChild(card);
        } else {
            ratiosGridEfficiency.appendChild(card);
        }
    });
}

// ==========================================================================
// Growth Analysis Engine
// ==========================================================================
async function loadGrowthData() {
    if (!state.ticker) return;
    const ticker = state.ticker;
    const cacheKey = `growth_${ticker}`;

    if (financialsLoader) {
        if (financialsLoaderText) financialsLoaderText.textContent = "Calculating CAGR and historical growth rates...";
        financialsLoader.style.display = "flex";
    }
    if (financialsError) financialsError.style.display = "none";

    try {
        let data = state.financialsCache[cacheKey];
        if (!data) {
            const resp = await fetch(`/api/financials/${encodeURIComponent(ticker)}/growth`);
            if (!resp.ok) {
                const errData = await resp.json().catch(() => ({}));
                throw new Error(errData.detail || "Unable to calculate growth analysis.");
            }
            data = await resp.json();
            state.financialsCache[cacheKey] = data;
        }

        renderGrowthView(data);
    } catch (err) {
        console.warn("Growth loading error:", err);
        showFinancialsError("Growth Analysis Unavailable", err.message);
    } finally {
        if (financialsLoader) financialsLoader.style.display = "none";
    }
}

function renderGrowthView(data) {
    if (!growthCardsGrid) return;
    growthCardsGrid.innerHTML = "";

    const metrics = data.metrics || [];
    const periods = data.periods_analyzed || [];

    if (metrics.length === 0) {
        growthCardsGrid.innerHTML = `<div class="growth-note">Insufficient historical annual periods to compute growth metrics.</div>`;
        return;
    }

    metrics.forEach(m => {
        const card = document.createElement("div");
        card.className = "growth-card";

        const header = document.createElement("div");
        header.className = "growth-card-header";

        const title = document.createElement("span");
        title.className = "growth-metric-title";
        title.textContent = m.metric;

        const badge = document.createElement("span");
        badge.className = "growth-period-badge";
        badge.textContent = periods.length > 0 ? `${periods[periods.length - 1]} to ${periods[0]}` : "Historical";

        header.appendChild(title);
        header.appendChild(badge);
        card.appendChild(header);

        const statsGrid = document.createElement("div");
        statsGrid.className = "growth-stats-grid";

        const yoyBox = document.createElement("div");
        yoyBox.className = "growth-stat-box";
        yoyBox.innerHTML = `
            <span class="growth-stat-label">YoY Growth</span>
            ${formatGrowthVal(m.yoy_growth)}
        `;
        statsGrid.appendChild(yoyBox);

        const cagr3Box = document.createElement("div");
        cagr3Box.className = "growth-stat-box";
        cagr3Box.innerHTML = `
            <span class="growth-stat-label">3-Year CAGR</span>
            ${formatGrowthVal(m.cagr_3y)}
        `;
        statsGrid.appendChild(cagr3Box);

        const cagr5Box = document.createElement("div");
        cagr5Box.className = "growth-stat-box";
        cagr5Box.innerHTML = `
            <span class="growth-stat-label">5-Year CAGR</span>
            ${formatGrowthVal(m.cagr_5y)}
        `;
        statsGrid.appendChild(cagr5Box);

        card.appendChild(statsGrid);

        if (m.notes) {
            const notesEl = document.createElement("div");
            notesEl.className = "growth-card-notes";
            notesEl.textContent = `Note: ${m.notes}`;
            card.appendChild(notesEl);
        }

        growthCardsGrid.appendChild(card);
    });
}

// ==========================================================================
// DOM Initialization & Event Bindings
// ==========================================================================
document.addEventListener("DOMContentLoaded", () => {
    // 1. Search Form Submission
    if (searchForm) {
        searchForm.addEventListener("submit", e => {
            e.preventDefault();
            const query = searchInput ? searchInput.value.trim() : "";
            if (searchDropdown) searchDropdown.style.display = "none";
            if (query) {
                loadStock(query);
            }
        });
    }

    // 2. Search Input Typing with Debounce
    if (searchInput) {
        searchInput.addEventListener("input", () => {
            const val = searchInput.value;
            if (clearSearchBtn) clearSearchBtn.style.display = val ? "flex" : "none";

            clearTimeout(searchDebounceTimer);
            searchDebounceTimer = setTimeout(() => {
                performSearch(val);
            }, 280);
        });
    }

    // Clear Search Input Button
    if (clearSearchBtn) {
        clearSearchBtn.addEventListener("click", () => {
            if (searchInput) {
                searchInput.value = "";
                searchInput.focus();
            }
            clearSearchBtn.style.display = "none";
            if (searchDropdown) searchDropdown.style.display = "none";
        });
    }

    // Close Dropdowns on Click Outside
    document.addEventListener("click", e => {
        if (searchForm && searchDropdown && !searchForm.contains(e.target) && !searchDropdown.contains(e.target)) {
            searchDropdown.style.display = "none";
        }
        if (indicatorDropdownBtn && indicatorMenu && !indicatorDropdownBtn.contains(e.target) && !indicatorMenu.contains(e.target)) {
            indicatorMenu.style.display = "none";
        }
    });

    // 3. Quick Trending Tickers
    document.querySelectorAll(".quick-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            const sym = chip.getAttribute("data-ticker");
            if (searchInput) searchInput.value = sym;
            loadStock(sym);
        });
    });

    // 4. Time Period Buttons
    periodButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const p = btn.getAttribute("data-period");
            changePeriod(p);
        });
    });

    // 5. Chart Type Toggles
    if (toggleCandlestick) {
        toggleCandlestick.addEventListener("click", () => {
            if (state.chartType === "candlestick") return;
            state.chartType = "candlestick";
            toggleCandlestick.classList.add("active");
            if (toggleLine) toggleLine.classList.remove("active");
            renderChart();
        });
    }

    if (toggleLine) {
        toggleLine.addEventListener("click", () => {
            if (state.chartType === "line") return;
            state.chartType = "line";
            toggleLine.classList.add("active");
            if (toggleCandlestick) toggleCandlestick.classList.remove("active");
            renderChart();
        });
    }

    // 6. Technical Indicators Menu
    if (indicatorDropdownBtn && indicatorMenu) {
        indicatorDropdownBtn.addEventListener("click", e => {
            e.stopPropagation();
            const isVisible = indicatorMenu.style.display === "block";
            indicatorMenu.style.display = isVisible ? "none" : "block";
        });
    }

    if (closeIndMenuBtn && indicatorMenu) {
        closeIndMenuBtn.addEventListener("click", () => {
            indicatorMenu.style.display = "none";
        });
    }

    document.querySelectorAll(".ind-option input[type='checkbox']").forEach(cb => {
        cb.addEventListener("change", e => {
            const id = e.target.getAttribute("data-id");
            toggleIndicator(id, e.target.checked);
        });
    });

    if (clearAllIndicatorsBtn) {
        clearAllIndicatorsBtn.addEventListener("click", () => {
            state.activeIndicators.clear();
            syncIndicatorCheckboxes();
            updateActiveIndicatorChips();
            state.indicatorsData = {};
            renderChart();
        });
    }

    // 7. Master Navigation Bar Tabs (Event Delegation)
    if (masterTabsGroup) {
        masterTabsGroup.addEventListener("click", e => {
            const btn = e.target.closest("button[data-tab]");
            if (!btn) return;
            const tab = btn.getAttribute("data-tab");
            switchMasterTab(tab);
        });
    }

    // 8. Frequency Selector Pills (Event Delegation)
    if (frequencyPillsGroup) {
        frequencyPillsGroup.addEventListener("click", e => {
            const btn = e.target.closest("button[data-freq]");
            if (!btn) return;
            const freq = btn.getAttribute("data-freq");
            switchFrequency(freq);
        });
    }

    // 9. Alert Banner Close Button
    if (alertCloseBtn) {
        alertCloseBtn.addEventListener("click", hideAlert);
    }

    // 10. Live Polling Manual Toggle Button
    if (liveToggleBtn) {
        liveToggleBtn.addEventListener("click", () => {
            state.isLivePollingActive = !state.isLivePollingActive;
            if (state.isLivePollingActive) {
                startLivePolling();
                pollLivePrice();
            } else {
                stopLivePolling();
            }
        });
    }

    // 11. Page Visibility & Focus for Live Polling
    document.addEventListener("visibilitychange", () => {
        if (document.hidden) {
            stopLivePolling();
        } else if (state.isLivePollingActive) {
            startLivePolling();
            pollLivePrice();
        }
    });

    window.addEventListener("focus", () => {
        if (state.isLivePollingActive && !state.livePollTimer) {
            startLivePolling();
            pollLivePrice();
        }
    });

    // 12. Window Resize Handler
    window.addEventListener("resize", () => {
        if (state.activeTab === "chart") {
            try { Plotly.Plots.resize("plotly-chart"); } catch (e) {}
        } else if (contextualFinChart && contextualChartBox && contextualChartBox.style.display !== "none") {
            try { Plotly.Plots.resize(contextualFinChart); } catch (e) {}
        }
    });

    // Set Default Indicator: SMA 50
    state.activeIndicators.add("SMA_50");
    syncIndicatorCheckboxes();
    updateActiveIndicatorChips();

    // Initial Load: Reliance Industries
    loadStock("RELIANCE.NS", "1y");
});
