import unittest
from datetime import datetime

from core.time.scoring import calculate_time_score, get_time_multiplier


class TestTimeScoring(unittest.TestCase):
    def test_calculate_time_score_uses_reference_time_when_provided(self):
        reference = datetime(2026, 1, 31).timestamp()
        file_time = datetime(2026, 1, 30).timestamp()

        score = calculate_time_score(file_time, reference_time=reference, decay_days=30)

        self.assertGreater(score, 0.9)
        self.assertLessEqual(score, 1.0)

    def test_calculate_time_score_future_timestamp_returns_one(self):
        now = datetime(2026, 1, 1).timestamp()
        future = datetime(2026, 1, 2).timestamp()

        score = calculate_time_score(future, reference_time=now, decay_days=30)

        self.assertEqual(score, 1.0)

    def test_get_time_multiplier_chooses_highest_keyword_multiplier(self):
        query = "latest report from yesterday"
        multiplier = get_time_multiplier(query)
        self.assertEqual(multiplier, 1.8)

    def test_get_time_multiplier_defaults_to_one(self):
        multiplier = get_time_multiplier("architecture notes")
        self.assertEqual(multiplier, 1.0)


if __name__ == "__main__":
    unittest.main()
