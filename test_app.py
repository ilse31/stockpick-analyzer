import unittest
from unittest.mock import patch

from app import estimate, evaluate, outcomes, replay_trade, lookup_stock


class ModelTests(unittest.TestCase):
    def test_tp_uses_intraday_high_separately_from_close(self):
        prices = [(100, 100)] * 21 + [(98, 105), (102, 103)]
        samples, _ = outcomes(prices, 2)
        self.assertEqual(len(samples), 1)
        _, _, change, upside = samples[0]
        self.assertAlmostEqual(change, .02)
        self.assertAlmostEqual(upside, .05)

    def test_intraday_exit_checks_stop_before_tp_when_both_touch(self):
        bar = {"open": 100, "low": 96, "high": 105, "close": 101}
        self.assertEqual(replay_trade([[("09:00", bar)]], 100, .04, .03), ("stop", 1, "09:00"))

    def test_open_above_entry_limit_is_skipped(self):
        bar = {"open": 101, "low": 99, "high": 105, "close": 101}
        self.assertIsNone(replay_trade([[("09:00", bar)]], 100, .04, .03))

    def test_intraday_tp_records_session_and_bar(self):
        quiet = {"open": 100, "low": 99, "high": 101, "close": 100}
        hit = dict(quiet, high=105)
        days = [[("09:00", quiet)], [("09:00", quiet), ("09:15", hit)]]
        self.assertEqual(replay_trade(days, 100, .04, .03), ("tp", 2, "09:15"))

    @patch("app.latest_sessions")
    @patch("app.listed_stocks", return_value=[])
    def test_lookup_rejects_unknown_stock_before_fetching_history(self, listed, sessions):
        self.assertIsNone(lookup_stock("XXXX"))
        sessions.assert_not_called()

    @patch("app.analyze", return_value=("skipped", {}, 4900))
    @patch("app.latest_sessions", return_value=["2026-11-04"])
    @patch("app.listed_stocks", return_value=[{"symbol": "BBCA", "name": "Bank Central Asia"}])
    def test_lookup_returns_price_even_without_trade_plan(self, listed, sessions, analyze):
        result = lookup_stock("BBCA")
        self.assertEqual(result["stock"]["close"], 4900)
        self.assertEqual(result["ranks"], {"1": [], "5": []})

    def test_unresolved_labels_are_excluded(self):
        known = [(i, 1, .02, .04) for i in range(40)]
        unresolved = [(40, 1, -.5, 0)] * 100
        self.assertEqual(estimate(known + unresolved, 1, 44, 5), estimate(known, 1, 44, 5))

    def test_direction_and_tp_backtest_have_distinct_outcomes(self):
        samples = [(i, i % 2, .02 if i % 2 else -.01, .04) for i in range(320)]
        result = evaluate(samples, 1, 320, 1)
        self.assertEqual(result["accuracy"], 1)
        self.assertEqual(result["tp_hit"], 1)
        self.assertLess(result["brier"], result["baseline_brier"])


if __name__ == "__main__":
    unittest.main()
