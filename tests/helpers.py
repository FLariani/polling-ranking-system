from pathlib import Path
from typing import Sequence, Tuple

import main
from flask.testing import FlaskClient
from models import Item


def create_test_client(tmp_path: Path) -> Tuple[FlaskClient, Sequence[Item], main.SessionInfo, main.DataStorage]:
    config_path = tmp_path / "items.txt"
    config_path.write_text("Apple\nBanana\nCherry\n", encoding="utf-8")

    data_dir = tmp_path / "data"
    main.init_app(config_path, data_dir)

    return main.app.test_client(), main.items, main.current_session, main.storage


def rank_form_data(voter_name: str, items: Sequence[Item]) -> dict:
    form_data = {"voter_name": voter_name}
    form_data.update({f"rank_{index + 1}": str(item.id) for index, item in enumerate(items)})
    return form_data
