"""Regression coverage for prediction-market expiry filtering."""
from datetime import datetime, timezone
from pathlib import Path
import sys
from unittest.mock import patch
import unittest

FETCHERS = Path(__file__).resolve().parents[1] / "scripts" / "fetchers"
sys.path.insert(0, str(FETCHERS))
import polymarket  # noqa: E402


NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)


class PolymarketFreshnessTests(unittest.TestCase):
    def test_rejects_question_with_explicit_past_deadline(self):
        market = {"question": "Gemini 4.0 released by September 30, 2026?"}
        self.assertFalse(polymarket.market_is_current(market, {}, NOW))

    def test_keeps_question_with_explicit_future_deadline(self):
        market = {"question": "Will OpenAI release GPT-6 by December 31, 2026?"}
        self.assertTrue(polymarket.market_is_current(market, {}, NOW))

    def test_rejects_closed_market_even_when_its_parent_event_is_active(self):
        market = {"question": "Gemini 4.0 released by September 30, 2026?", "closed": True}
        event = {"active": True, "closed": False}
        self.assertFalse(polymarket.market_is_current(market, event, NOW))

    def test_rejects_api_market_end_date_in_the_past(self):
        market = {"question": "Will a model ship?", "endDate": "2026-09-30T12:00:00Z"}
        self.assertFalse(polymarket.market_is_current(market, {}, NOW))

    def test_rejects_event_end_date_in_the_past(self):
        market = {"question": "Will a model ship?"}
        event = {"endDate": "2026-09-30T12:00:00Z"}
        self.assertFalse(polymarket.market_is_current(market, event, NOW))

    def test_main_does_not_write_closed_market_returned_by_active_event_search(self):
        closed_market = {
            "conditionId": "closed-gemini",
            "question": "Gemini 4.0 released by September 30, 2026?",
            "closed": True,
            "volumeNum": 644216,
            "outcomePrices": "[\"0\", \"1\"]",
            "oneDayPriceChange": -0.25,
        }
        payload = {"events": [{"title": "Gemini 4.0 released by...?", "active": True,
                                "closed": False, "slug": "gemini-4pt0-released-by-june-30-2026",
                                "markets": [closed_market]}]}
        written = []
        with patch.object(polymarket, "get", return_value=__import__("json").dumps(payload)), \
             patch.object(polymarket, "out_path", return_value="/tmp/polymarket.json"), \
             patch.object(polymarket, "atomic_write_json", side_effect=lambda _path, data: written.extend(data)):
            polymarket.main()
        self.assertEqual(written, [])

    def test_rejects_market_not_accepting_orders(self):
        self.assertFalse(polymarket.market_is_current(
            {'question': 'Will AI ship by December 31, 2026?', 'acceptingOrders': False}, {}, NOW))

    def test_normalized_output_retains_status_deadline_and_binary_yes_value(self):
        import json
        market = dict(conditionId='synthetic-open', question='Will an AI model ship by December 31, 2030?',
            closed=False, active=True, acceptingOrders=True, endDate='2030-12-31T23:59:59Z',
            outcomes='["No", "Yes"]', outcomePrices='["0.995", "0.005"]', volumeNum=100000,
            oneDayPriceChange=0.001)
        payload = dict(events=[dict(title='AI model release', slug='synthetic-model', active=True,
                                   closed=False, markets=[market])])
        written = []
        with patch.object(polymarket, 'get', return_value=json.dumps(payload)), \
             patch.object(polymarket, 'out_path', return_value='unused-test-output'), \
             patch.object(polymarket, 'atomic_write_json', side_effect=lambda path, data: written.extend(data)):
            polymarket.main()
        self.assertEqual(len(written), 1)
        self.assertEqual(written[0]['yes_pct'], 0.5)
        self.assertEqual(written[0]['endDate'], market['endDate'])
        self.assertIs(written[0]['closed'], False)

    def test_total_search_outage_is_failure_not_empty_success(self):
        with patch.object(polymarket, 'get', side_effect=OSError('synthetic unavailable')), \
             patch.object(polymarket, 'out_path', return_value='unused-test-output'), \
             patch.object(polymarket, 'atomic_write_json'):
            self.assertEqual(polymarket.main(), 1)
        with patch.object(polymarket, 'get', return_value='{"events": []}'), \
             patch.object(polymarket, 'out_path', return_value='unused-test-output'), \
             patch.object(polymarket, 'atomic_write_json'):
            self.assertEqual(polymarket.main(), 0)

    def test_keeps_undated_open_ended_market(self):
        market = {"question": "Will OpenAI announce AGI before 2027?"}
        self.assertTrue(polymarket.market_is_current(market, {}, NOW))


if __name__ == "__main__":
    unittest.main()
