"""
Flask web application entry point.

Routes are defined here. Each route maps a URL to a Python function that
reads the request, does work, and returns an HTML response.
"""

import argparse
import atexit
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from flask import Flask, redirect, render_template, request, url_for

from data_storage import DataStorage, SessionInfo, TIMESTAMP_FMT
from models import Item
from randomization import seed_rng, shuffled_items
from results_calculator import calculate_results, filter_votes_by_time

app = Flask(__name__)

# Module-level globals hold shared state between requests.
# Flask handles one request at a time in dev mode, so this is safe here.
storage: Optional[DataStorage] = None
items: List[Item] = []
current_session: Optional[SessionInfo] = None


def cleanup() -> None:
    # Registered with atexit so it runs when the server shuts down.
    # Currently a no-op — Python handles memory automatically — but the
    # hook is here if teardown logic is needed later.
    pass


@app.route("/")
def index():
    """Show the voting ballot. Items are shuffled on every page load to reduce position bias."""
    if not items:
        return render_template("message.html", title="Configuration Error", message="No items loaded.")

    voter_name = request.args.get("voter_name", "")
    randomized = shuffled_items(items)  # new random order each time
    return render_template("vote.html", items=randomized, voter_name=voter_name)


@app.route("/submit_vote", methods=["POST"])
def submit_vote():
    """Accept a ranked ballot from the form and save it to disk.

    The form sends one hidden field per rank position (rank_1, rank_2 …).
    We read them in order to reconstruct the voter's full ranking.
    """
    global current_session
    if not current_session:
        return render_template("message.html", title="Session Error", message="No active session.")

    voter_name = request.form.get("voter_name", "").strip() or "Anonymous"
    ordered_ids: List[int] = []
    used = set()

    for i in range(1, len(items) + 1):
        key = f"rank_{i}"
        val = request.form.get(key)
        if not val:
            return render_template("message.html", title="Input Error", message="All rank selections are required.")
        item_id = int(val)
        if item_id in used:
            return render_template("message.html", title="Input Error", message="Each rank must map to a different item.")
        used.add(item_id)
        ordered_ids.append(item_id)

    # Sanity-check: the submitted IDs must match the known item set exactly
    if set(ordered_ids) != {it.id for it in items}:
        return render_template("message.html", title="Input Error", message="Invalid ranking data submitted.")

    try:
        revote = storage.save_vote_set(current_session, voter_name, ordered_ids)
    except RuntimeError as ex:
        # save_vote_set raises RuntimeError when the session is closed
        return render_template("message.html", title="Session Closed", message=str(ex))

    if revote:
        msg = f"Vote updated for {voter_name}."
    else:
        msg = f"Vote recorded for {voter_name}."
    return render_template("message.html", title="Vote Submitted", message=msg)


@app.route("/admin")
def admin():
    """Show the admin dashboard with the current session status."""
    status = storage.read_session_status(current_session) if current_session else "closed"
    return render_template("admin.html", session=current_session, status=status)


@app.route("/admin/close", methods=["POST"])
def close_session():
    """Close the session so no new votes can be submitted."""
    if not current_session:
        return render_template("message.html", title="Session Error", message="No active session.")
    storage.set_session_status(current_session, "closed")
    return redirect(url_for("admin"))


@app.route("/admin/open", methods=["POST"])
def open_session():
    """Re-open a closed session to allow voting again."""
    if not current_session:
        return render_template("message.html", title="Session Error", message="No active session.")
    storage.set_session_status(current_session, "open")
    return redirect(url_for("admin"))


@app.route("/results")
def results():
    """Display current results, optionally filtered to a time window via query params."""
    if not current_session:
        return render_template("message.html", title="Session Error", message="No active session.")

    start_s = request.args.get("start", "").strip()
    end_s = request.args.get("end", "").strip()

    # Parse the optional time-filter params; leave as None if not provided
    start = datetime.strptime(start_s, TIMESTAMP_FMT) if start_s else None
    end = datetime.strptime(end_s, TIMESTAMP_FMT) if end_s else None

    all_votes = storage.load_votes(current_session)
    votes = filter_votes_by_time(all_votes, start=start, end=end)
    rows = calculate_results(items, votes)
    return render_template("results.html", rows=rows, start=start_s, end=end_s, fmt=TIMESTAMP_FMT)


@app.route("/export_results", methods=["POST"])
def export_results():
    """Write results to a .txt CSV file in the data directory and confirm to the user."""
    if not current_session:
        return render_template("message.html", title="Session Error", message="No active session.")

    all_votes = storage.load_votes(current_session)
    rows = calculate_results(items, all_votes)
    payload = [
        {
            "item_name": r.item_name,
            "average_rank": f"{r.average_rank:.4f}" if r.vote_count else "",
            "vote_count": str(r.vote_count),
        }
        for r in rows
    ]

    out_name = f"results_{current_session.session_id}.txt"
    out_path = storage.base_dir / out_name
    storage.export_results(out_path, payload)
    return render_template("message.html", title="Export Complete", message=f"Results exported to {out_path}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments so the app can be configured without editing code."""
    parser = argparse.ArgumentParser(description="Bias-Free Polling and Ranking")
    parser.add_argument(
        "--config",
        default="config/items.txt",
        help="Path to item configuration file (default: config/items.txt)",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=5000, type=int)
    return parser.parse_args()


def init_app(config_path: Path = Path("config/items.txt"), data_dir: Path = Path("data")) -> None:
    """Initialise storage, load items, and create a new session.

    Extracted from __main__ so tests can call it directly without starting the
    HTTP server — this is the standard pattern for making Flask apps testable.
    """
    global storage, items, current_session

    storage = DataStorage(data_dir)
    items = storage.load_items_from_config(config_path)

    seed_rng()
    current_session = storage.create_session()


def bootstrap() -> argparse.Namespace:
    """Parse args and initialise the app; returns args so the caller knows host/port."""
    args = parse_args()
    init_app(Path(args.config), Path("data"))
    return args


if __name__ == "__main__":
    atexit.register(cleanup)
    run_args = bootstrap()
    app.run(host=run_args.host, port=run_args.port, debug=False)
