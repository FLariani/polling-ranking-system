"""
Unit tests for results_calculator and data_storage.

Unit tests focus on one function at a time and use only in-memory data or a
temporary directory — no running server needed.  This keeps them fast and makes
failures easy to pinpoint.
"""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from models import Item, Vote
from results_calculator import calculate_results, filter_votes_by_time
from data_storage import DataStorage, MAX_ITEM_NAME


class TestCalculateResults(unittest.TestCase):
    """Tests for calculate_results — the core tallying logic."""

    def test_no_votes(self):
        # With no votes every item should have a zero count and zero average.
        # This tests the empty-list edge case so the results page doesn't crash
        # when a session has received no submissions yet.
        items = [Item(id=1, item_name="Apple"), Item(id=2, item_name="Banana")]
        rows = calculate_results(items, [])

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].vote_count, 0)
        self.assertEqual(rows[0].average_rank, 0.0)
        self.assertEqual(rows[1].vote_count, 0)

    def test_with_votes(self):
        # Alice ranked Apple first and Banana second, so Apple's average should be 1.0
        # and Banana's should be 2.0.  Confirms the basic arithmetic is correct.
        items = [Item(id=1, item_name="Apple"), Item(id=2, item_name="Banana")]
        votes = [
            Vote(voter_name="Alice", item_id=1, rank=1, timestamp=datetime.now()),
            Vote(voter_name="Alice", item_id=2, rank=2, timestamp=datetime.now()),
        ]

        rows = calculate_results(items, votes)

        self.assertEqual(rows[0].item_name, "Apple")
        self.assertEqual(rows[0].average_rank, 1.0)
        self.assertEqual(rows[0].vote_count, 1)
        self.assertEqual(rows[1].average_rank, 2.0)


class TestFilterVotesByTime(unittest.TestCase):
    """Tests for filter_votes_by_time — the time-window filtering logic."""

    def test_filter_votes_by_time(self):
        # Alice voted before noon and Bob voted after noon.
        # Filtering with start=noon should keep only Bob's vote.
        # This confirms that the start boundary is exclusive (strictly after).
        now = datetime(2026, 4, 8, 12, 0, 0)
        votes = [
            Vote(voter_name="Alice", item_id=1, rank=1, timestamp=datetime(2026, 4, 8, 11, 0, 0)),
            Vote(voter_name="Bob", item_id=1, rank=2, timestamp=datetime(2026, 4, 8, 13, 0, 0)),
        ]

        filtered = filter_votes_by_time(votes, start=now, end=None)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].voter_name, "Bob")


class TestLoadItemsFromConfig(unittest.TestCase):
    """Tests for DataStorage.load_items_from_config — config file parsing."""

    def setUp(self):
        # Each test gets a fresh temporary directory so leftover files from
        # one test can never affect another.
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self):
        # Clean up the temporary directory after every test.
        self._tmp.cleanup()

    def test_load_items_from_config(self):
        # A valid two-item config should produce two Item objects in order.
        config_path = self.tmp_path / "items.txt"
        config_path.write_text("Apple\nBanana\n", encoding="utf-8")

        storage = DataStorage(self.tmp_path / "data")
        items = storage.load_items_from_config(config_path)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].item_name, "Apple")

    def test_load_items_from_config_raises_on_too_long_name(self):
        # A name longer than MAX_ITEM_NAME should be rejected immediately.
        # Testing this prevents oversized data from quietly reaching the database
        # or the UI where it could cause display or storage problems.
        config_path = self.tmp_path / "items.txt"
        config_path.write_text("A" * (MAX_ITEM_NAME + 1) + "\nBanana\n", encoding="utf-8")

        storage = DataStorage(self.tmp_path / "data")
        with self.assertRaises(ValueError):
            storage.load_items_from_config(config_path)
