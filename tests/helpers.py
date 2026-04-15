"""
Shared test utilities.

Centralising setup here means each test file can call one function instead of
repeating the same boilerplate to spin up a Flask test client.
"""

from pathlib import Path
from typing import Sequence, Tuple

import main
from flask.testing import FlaskClient
from models import Item


def create_test_client(tmp_path: Path) -> Tuple[FlaskClient, Sequence[Item], main.SessionInfo, main.DataStorage]:
    """Initialise the app with a temporary config and data directory, then return the test client.

    Using a tmp_path for every call means each test gets a clean slate —
    votes from one test can't leak into another.

    After init_app the session is None (admin must create it explicitly), so we
    POST to /admin/create here to produce a ready-to-use ranking session.
    """
    config_path = tmp_path / "items.txt"
    config_path.write_text("Apple\nBanana\nCherry\n", encoding="utf-8")  # minimal valid config

    data_dir = tmp_path / "data"
    main.init_app(config_path, data_dir)

    client = main.app.test_client()
    # Create a default non-anonymous ranking session so tests can vote immediately.
    client.post("/admin/create", data={"session_type": "ranking"})

    return client, main.items, main.current_session, main.storage


def rank_form_data(voter_name: str, items: Sequence[Item]) -> dict:
    """Build the POST body that the /submit_vote route expects.

    The route reads rank_1, rank_2 … in order, so we zip the rank position
    with each item's ID to produce the correct field names.
    """
    form_data = {"voter_name": voter_name}
    form_data.update({f"rank_{index + 1}": str(item.id) for index, item in enumerate(items)})
    return form_data
