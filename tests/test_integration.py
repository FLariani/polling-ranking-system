"""
Integration test for the full vote flow.

Integration tests exercise the whole stack — HTTP routing, storage, and results —
by sending real requests through Flask's test client.  One test covers the entire
user journey so we catch any breakage where two components interact.
"""

import csv
import tempfile
import unittest
from pathlib import Path

from tests.helpers import create_test_client, rank_form_data


class TestFullVoteFlow(unittest.TestCase):
    """Walks through every major action a user and admin can perform."""

    def setUp(self):
        # A fresh temp directory per test guarantees isolation — votes from
        # a previous run can't interfere with this one.
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.client, self.items, self.session, self.storage = create_test_client(self.tmp_path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_full_vote_flow(self):
        client = self.client
        items = self.items
        session = self.session
        storage = self.storage

        # ── Step 1: ballot loads and shows all items ──────────────────────
        # Confirms the /vote route works and that every item name appears in
        # the HTML so voters can actually see what they're ranking.
        response = client.get("/vote")
        self.assertEqual(response.status_code, 200)
        for item in items:
            self.assertIn(item.item_name.encode(), response.data)

        # ── Step 2: first vote is accepted ────────────────────────────────
        # rank_form_data builds the rank_1 … rank_N fields the route expects.
        # We check the confirmation message to prove the vote was recorded.
        form_data = rank_form_data("Alice", items)
        response = client.post("/submit_vote", data=form_data)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Vote recorded for Alice", response.data)

        # ── Step 3: duplicate vote is rejected ───────────────────────────
        # Submitting again with the same name (case-insensitive) should be
        # blocked — each person may only vote once per session.
        reversed_ids = [str(item.id) for item in reversed(items)]
        revote_data = {"voter_name": "alice", **{f"rank_{i + 1}": reversed_ids[i] for i in range(len(items))}}
        response = client.post("/submit_vote", data=revote_data)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"already voted", response.data)

        # ── Step 4: closing the session blocks further votes ──────────────
        response = client.post("/admin/close", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"closed" in response.data or b"Session" in response.data)

        # Use a fresh name that hasn't voted yet so the closed-session check
        # is reached rather than the duplicate-vote check.
        charlie_data = rank_form_data("Charlie", items)
        response = client.post("/submit_vote", data=charlie_data)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Session is closed", response.data)

        # ── Step 5: re-opening the session allows voting again ────────────
        response = client.post("/admin/open", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"open" in response.data or b"Session" in response.data)

        # Charlie hasn't voted yet, so their first vote should be accepted now the session is open.
        response = client.post("/submit_vote", data=charlie_data)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Vote recorded for Charlie", response.data)

        # ── Step 6: results page lists every item ─────────────────────────
        # We don't check exact rankings here — that's covered by the unit tests.
        # We just confirm all items appear so the page isn't blank.
        response = client.get("/results")
        self.assertEqual(response.status_code, 200)
        for item in items:
            self.assertIn(item.item_name.encode(), response.data)

        # ── Step 7: export writes a valid CSV to disk ─────────────────────
        # Checks that the file exists, has the right number of rows, and that
        # the item_name column contains real data.
        response = client.post("/export_results")
        self.assertEqual(response.status_code, 200)
        expected_export = storage.base_dir / f"results_{session.session_id}.txt"
        self.assertTrue(expected_export.exists())
        with expected_export.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(len(rows), len(items))
        self.assertIn(rows[0]["item_name"], {item.item_name for item in items})
