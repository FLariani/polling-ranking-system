from pathlib import Path

import pytest

from tests.helpers import create_test_client


@pytest.fixture
def app_context(tmp_path: Path):
    client, items, session, storage = create_test_client(tmp_path)
    return {
        "client": client,
        "items": items,
        "session": session,
        "storage": storage,
    }
