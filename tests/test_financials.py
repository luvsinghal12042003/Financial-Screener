import unittest
import pandas as pd
import numpy as np
from datetime import datetime

from backend.services.financials import (
    STANDARD_LABEL_MAP,
    _safe_float,
    _format_date,
    _build_statement_response,
    _compute_ttm_statement,
    _find_item_value,
    get_financial_statement,
    calculate_financial_ratios,
    calculate_growth_analysis,
)
from backend.models.schemas import (
    FinancialStatementResponse,
    FinancialRatiosResponse,
    GrowthResponse,
)


class TestFinancialStatementNormalization(unittest.TestCase):
    def test_safe_float_conversions(self):
        self.assertEqual(_safe_float(1234.567), 1234.57)
        self.assertEqual(_safe_float(100), 100.0)
        self.assertIsNone(_safe_float(None))
        self.assertIsNone(_safe_float(np.nan))
        self.assertIsNone(_safe_float(float("nan")))
        self.assertIsNone(_safe_float(float("inf")))
        self.assertIsNone(_safe_float(float("-inf")))
        self.assertIsNone(_safe_float("invalid_string"))

    def test_standard_label_mapping_preserves_originals(self):
        self.assertIn("Total Revenue", STANDARD_LABEL_MAP)
        self.assertIn("Operating Income", STANDARD_LABEL_MAP)
        self.assertIn("Net Income", STANDARD_LABEL_MAP)
        self.assertIn("Operating Cash Flow", STANDARD_LABEL_MAP)
        self.assertIn("Capital Expenditure", STANDARD_LABEL_MAP)

    def test_statement_builder_handles_dataframe_and_nans(self):
        # Create a mock DataFrame simulating yfinance output
        data = {
            pd.Timestamp("2024-03-31"): [100000.0, 25000.0, np.nan],
            pd.Timestamp("2023-03-31"): [90000.0, 20000.0, 5000.0],
        }
        df = pd.DataFrame(data, index=["Total Revenue", "Operating Income", "Tax Provision"])

        resp = _build_statement_response(
            ticker="TEST.NS",
            company_name="Test Industries Ltd",
            statement_type="income_statement",
            frequency="annual",
            currency="INR",
            df=df
        )

        self.assertIsInstance(resp, FinancialStatementResponse)
        self.assertEqual(resp.ticker, "TEST.NS")
        self.assertEqual(resp.currency, "INR")
        self.assertEqual(len(resp.periods), 2)
        self.assertEqual(resp.periods[0], "2024-03-31")
        self.assertEqual(resp.periods[1], "2023-03-31")

        # Verify line items
        line_item_names = [item.name for item in resp.line_items]
        self.assertIn("Total Revenue", line_item_names)
        self.assertIn("Operating Income", line_item_names)
        self.assertIn("Tax Provision", line_item_names)

        # Verify missing data is None and NOT zero
        tax_item = next(item for item in resp.line_items if item.name == "Tax Provision")
        self.assertIsNone(tax_item.values["2024-03-31"])
        self.assertEqual(tax_item.values["2023-03-31"], 5000.0)

    def test_ttm_statement_computation(self):
        dates = [
            pd.Timestamp("2024-09-30"),
            pd.Timestamp("2024-06-30"),
            pd.Timestamp("2024-03-31"),
            pd.Timestamp("2023-12-31"),
        ]
        data = {
            d: [25000.0, 5000.0] for d in dates
        }
        q_df = pd.DataFrame(data, index=["Total Revenue", "Net Income"])

        ttm_df = _compute_ttm_statement(q_df)
        self.assertEqual(len(ttm_df.columns), 1)
        ttm_col = ttm_df.columns[0]
        self.assertIn("TTM", ttm_col)
        self.assertEqual(ttm_df.loc["Total Revenue", ttm_col], 100000.0)
        self.assertEqual(ttm_df.loc["Net Income", ttm_col], 20000.0)

    def test_ttm_statement_raises_on_insufficient_quarters(self):
        # Only 2 quarters provided
        dates = [pd.Timestamp("2024-09-30"), pd.Timestamp("2024-06-30")]
        data = {d: [25000.0] for d in dates}
        q_df = pd.DataFrame(data, index=["Total Revenue"])

        with self.assertRaises(ValueError):
            _compute_ttm_statement(q_df)


class TestFinancialRatiosLogic(unittest.TestCase):
    def test_find_item_value_synonyms(self):
        df = pd.DataFrame(
            {"2024-03-31": [15000.0]},
            index=["Cash Cash Equivalents And Short Term Investments"]
        )
        val = _find_item_value(df, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"], "2024-03-31")
        self.assertEqual(val, 15000.0)

        missing = _find_item_value(df, ["Nonexistent Item"], "2024-03-31")
        self.assertIsNone(missing)


class TestGrowthAnalysisLogic(unittest.TestCase):
    def test_cagr_calculation_safeguards(self):
        from backend.services.financials import calculate_growth_analysis
        # Verify growth calculation runs safely on actual tickers
        growth_resp = calculate_growth_analysis("AAPL")
        self.assertIsInstance(growth_resp, GrowthResponse)
        self.assertEqual(growth_resp.ticker, "AAPL")
        self.assertTrue(len(growth_resp.metrics) > 0)

        rev_metric = next((m for m in growth_resp.metrics if "Revenue" in m.metric), None)
        self.assertIsNotNone(rev_metric)


class TestLiveIntegrationTickers(unittest.TestCase):
    def test_reliance_financials(self):
        # 1. Income statement
        stmt = get_financial_statement("RELIANCE.NS", "income_statement", "annual")
        self.assertIsInstance(stmt, FinancialStatementResponse)
        self.assertEqual(stmt.ticker, "RELIANCE.NS")
        self.assertEqual(stmt.currency, "INR")
        self.assertTrue(len(stmt.periods) >= 3)
        self.assertTrue(len(stmt.line_items) > 10)

        # 2. Financial ratios
        ratios = calculate_financial_ratios("RELIANCE.NS")
        self.assertIsInstance(ratios, FinancialRatiosResponse)
        ratio_ids = [r.id for r in ratios.ratios]
        for req_id in ["PE", "PB", "ROE", "ROA", "DEBT_EQUITY", "CURRENT_RATIO", "OP_MARGIN", "NET_MARGIN", "ASSET_TURNOVER", "CFO_PAT", "FCF"]:
            self.assertIn(req_id, ratio_ids, f"Missing required ratio: {req_id}")
            # Ensure each ratio has a formula disclosed
            r_obj = next(r for r in ratios.ratios if r.id == req_id)
            self.assertTrue(len(r_obj.formula) > 0, f"Ratio {req_id} missing formula")

        # 3. Growth analysis
        growth = calculate_growth_analysis("RELIANCE.NS")
        self.assertIsInstance(growth, GrowthResponse)
        self.assertTrue(len(growth.metrics) >= 2)

    def test_tcs_financials(self):
        stmt = get_financial_statement("TCS.NS", "balance_sheet", "annual")
        self.assertEqual(stmt.ticker, "TCS.NS")
        self.assertEqual(stmt.currency, "INR")

        ratios = calculate_financial_ratios("TCS.NS")
        self.assertEqual(ratios.ticker, "TCS.NS")

    def test_aapl_financials(self):
        stmt = get_financial_statement("AAPL", "cash_flow", "annual")
        self.assertEqual(stmt.ticker, "AAPL")
        self.assertEqual(stmt.currency, "USD")

        ratios = calculate_financial_ratios("AAPL")
        self.assertEqual(ratios.ticker, "AAPL")


if __name__ == "__main__":
    unittest.main()
