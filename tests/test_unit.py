from datetime import datetime
from pathlib import Path

import pytest

from models import Item, Vote
from results_calculator import calculate_results, filter_votes_by_time
from data_storage import DataStorage, MAX_ITEM_NAME


def test_calculate_results_no_votes():
    items = [Item(id=1, item_name="Apple"), Item(id=2, item_name="Banana")]
    rows = calculate_results(items, [])

    assert len(rows) == 2
    assert rows[0].vote_count == 0
    assert rows[0].average_rank == 0.0
    assert rows[1].vote_count == 0


def test_calculate_results_with_votes():
    items = [Item(id=1, item_name="Apple"), Item(id=2, item_name="Banana")]
    votes = [
        Vote(voter_name="Alice", item_id=1, rank=1, timestamp=datetime.now()),
        Vote(voter_name="Alice", item_id=2, rank=2, timestamp=datetime.now()),
    ]

    rows = calculate_results(items, votes)

    assert rows[0].item_name == "Apple"
    assert rows[0].average_rank == 1.0
    assert rows[0].vote_count == 1
    assert rows[1].average_rank == 2.0


def test_filter_votes_by_time():
    now = datetime(2026, 4, 8, 12, 0, 0)
    votes = [
        Vote(voter_name="Alice", item_id=1, rank=1, timestamp=datetime(2026, 4, 8, 11, 0, 0)),
        Vote(voter_name="Bob", item_id=1, rank=2, timestamp=datetime(2026, 4, 8, 13, 0, 0)),
    ]

    filtered = filter_votes_by_time(votes, start=now, end=None)
    assert len(filtered) == 1
    assert filtered[0].voter_name == "Bob"


def test_load_items_from_config(tmp_path: Path):
    config_path = tmp_path / "items.txt"
    config_path.write_text("Apple\nBanana\n", encoding="utf-8")

    storage = DataStorage(tmp_path / "data")
    items = storage.load_items_from_config(config_path)

    assert len(items) == 2
    assert items[0].item_name == "Apple"


def test_load_items_from_config_raises_on_too_long_name(tmp_path: Path):
    config_path = tmp_path / "items.txt"
    config_path.write_text("A" * (MAX_ITEM_NAME + 1) + "\nBanana\n", encoding="utf-8")

    storage = DataStorage(tmp_path / "data")
    with pytest.raises(ValueError):
        storage.load_items_from_config(config_path)
