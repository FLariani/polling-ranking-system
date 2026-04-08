import csv

from tests.helpers import rank_form_data


def test_full_vote_flow(app_context):
    client = app_context["client"]
    items = app_context["items"]
    session = app_context["session"]
    storage = app_context["storage"]

    response = client.get("/")
    assert response.status_code == 200
    for item in items:
        assert item.item_name.encode() in response.data

    form_data = rank_form_data("Alice", items)
    response = client.post("/submit_vote", data=form_data)
    assert response.status_code == 200
    assert b"Vote recorded for Alice" in response.data

    reversed_ids = [str(item.id) for item in reversed(items)]
    revote_data = {"voter_name": "Alice", **{f"rank_{i + 1}": reversed_ids[i] for i in range(len(items))}}
    response = client.post("/submit_vote", data=revote_data)
    assert response.status_code == 200
    assert b"Vote updated for Alice" in response.data

    response = client.post("/admin/close", follow_redirects=True)
    assert response.status_code == 200
    assert b"closed" in response.data or b"Session" in response.data

    response = client.post("/submit_vote", data=form_data)
    assert response.status_code == 200
    assert b"Session is closed" in response.data

    response = client.post("/admin/open", follow_redirects=True)
    assert response.status_code == 200
    assert b"open" in response.data or b"Session" in response.data

    response = client.post("/submit_vote", data=form_data)
    assert response.status_code == 200
    assert b"Vote recorded for Alice" in response.data or b"Vote updated for Alice" in response.data

    response = client.get("/results")
    assert response.status_code == 200
    for item in items:
        assert item.item_name.encode() in response.data

    response = client.post("/export_results")
    assert response.status_code == 200
    expected_export = storage.base_dir / f"results_{session.session_id}.txt"
    assert expected_export.exists()
    with expected_export.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == len(items)
    assert rows[0]["item_name"] in {item.item_name for item in items}
