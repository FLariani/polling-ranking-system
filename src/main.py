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
storage: Optional[DataStorage] = None
items: List[Item] = []
current_session: Optional[SessionInfo] = None


def cleanup() -> None:
    pass


# ── Landing ───────────────────────────────────────────────────────────────────

@app.route("/")
def landing():
    """Home page — lets the user identify as admin or voter."""
    return render_template("landing.html", has_session=current_session is not None)


# ── Voter flow ────────────────────────────────────────────────────────────────

@app.route("/vote")
def vote():
    """Show the ballot. Layout adapts to session type and anonymous setting."""
    if not current_session:
        return render_template("message.html", title="No Active Session",
                               message="No session is open yet. Ask your admin to create one.")
    if storage.read_session_status(current_session) == "closed":
        return render_template("message.html", title="Session Closed",
                               message="Voting is currently closed.")

    randomized = shuffled_items(items)
    return render_template(
        "vote.html",
        items=randomized,
        session_type=current_session.session_type,
        anonymous=current_session.anonymous,
    )


@app.route("/submit_vote", methods=["POST"])
def submit_vote():
    """Accept a ballot and save it to disk.

    Handles both session types:
    - ranking: reads rank_1 … rank_N fields and stores the full ordered list.
    - voting:  reads a single item_id field and stores it as a one-item list.
    """
    if not current_session:
        return render_template("message.html", title="Session Error", message="No active session.")

    # In anonymous sessions the server ignores any name the form might send.
    if current_session.anonymous:
        voter_name = "Anonymous"
    else:
        voter_name = request.form.get("voter_name", "").strip() or "Anonymous"

    if current_session.session_type == "voting":
        val = request.form.get("item_id")
        if not val:
            return render_template("message.html", title="Input Error",
                                   message="Please select an item.")
        item_id = int(val)
        if item_id not in {it.id for it in items}:
            return render_template("message.html", title="Input Error",
                                   message="Invalid item selected.")
        ordered_ids = [item_id]
    else:
        # Ranking mode — collect rank_1 … rank_N in order.
        ordered_ids: List[int] = []
        used = set()
        for i in range(1, len(items) + 1):
            raw = request.form.get(f"rank_{i}")
            if not raw:
                return render_template("message.html", title="Input Error",
                                       message="All rank selections are required.")
            item_id = int(raw)
            if item_id in used:
                return render_template("message.html", title="Input Error",
                                       message="Each rank must map to a different item.")
            used.add(item_id)
            ordered_ids.append(item_id)

        if set(ordered_ids) != {it.id for it in items}:
            return render_template("message.html", title="Input Error",
                                   message="Invalid ranking data submitted.")

    try:
        revote = storage.save_vote_set(current_session, voter_name, ordered_ids)
    except RuntimeError as ex:
        return render_template("message.html", title="Session Closed", message=str(ex))

    action = "updated" if revote else "recorded"
    return render_template("message.html", title="Vote Submitted",
                           message=f"Vote {action} for {voter_name}.")


# ── Results ───────────────────────────────────────────────────────────────────

@app.route("/results")
def results():
    """Display current results, filtered by optional time window query params."""
    if not current_session:
        return render_template("message.html", title="Session Error", message="No active session.")

    start_s = request.args.get("start", "").strip()
    end_s   = request.args.get("end",   "").strip()

    start = datetime.strptime(start_s, TIMESTAMP_FMT) if start_s else None
    end   = datetime.strptime(end_s,   TIMESTAMP_FMT) if end_s   else None

    all_votes = storage.load_votes(current_session)
    votes     = filter_votes_by_time(all_votes, start=start, end=end)
    rows      = calculate_results(items, votes)

    # For voting mode the template only needs vote counts, not average ranks.
    total_voters = len({v.voter_name for v in votes}) if current_session.session_type == "voting" else 0

    return render_template(
        "results.html",
        rows=rows,
        start=start_s,
        end=end_s,
        fmt=TIMESTAMP_FMT,
        session_type=current_session.session_type,
        total_voters=total_voters,
    )


# ── Admin flow ────────────────────────────────────────────────────────────────

@app.route("/admin")
def admin():
    """Admin dashboard. Redirects to setup if no session exists yet."""
    if not current_session:
        return redirect(url_for("admin_setup"))
    status = storage.read_session_status(current_session)
    return render_template("admin.html", session=current_session, status=status)


@app.route("/admin/setup")
def admin_setup():
    """Session creation form — pick type and anonymous mode."""
    return render_template("admin_setup.html")


@app.route("/admin/create", methods=["POST"])
def admin_create():
    """Create a new session from the setup form and redirect to the dashboard."""
    global current_session
    session_type = request.form.get("session_type", "ranking")
    anonymous    = request.form.get("anonymous") == "on"
    current_session = storage.create_session(session_type=session_type, anonymous=anonymous)
    return redirect(url_for("admin"))


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


@app.route("/export_results", methods=["POST"])
def export_results():
    """Write results to a .txt CSV in the data directory and confirm to the user."""
    if not current_session:
        return render_template("message.html", title="Session Error", message="No active session.")

    all_votes = storage.load_votes(current_session)
    rows      = calculate_results(items, all_votes)
    payload   = [
        {
            "item_name":    r.item_name,
            "average_rank": f"{r.average_rank:.4f}" if r.vote_count else "",
            "vote_count":   str(r.vote_count),
        }
        for r in rows
    ]

    out_path = storage.base_dir / f"results_{current_session.session_id}.txt"
    storage.export_results(out_path, payload)
    return render_template("message.html", title="Export Complete",
                           message=f"Results exported to {out_path}")


# ── App init & entry point ────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments so the app can be configured without editing code."""
    parser = argparse.ArgumentParser(description="Bias-Free Polling and Ranking")
    parser.add_argument("--config", default="config/items.txt")
    parser.add_argument("--host",   default="127.0.0.1")
    parser.add_argument("--port",   default=5000, type=int)
    return parser.parse_args()


def init_app(config_path: Path = Path("config/items.txt"), data_dir: Path = Path("data")) -> None:
    """Initialise storage and load items. Does NOT create a session.

    The admin must visit /admin/setup and submit the creation form before
    voting is possible. This keeps session configuration explicit.
    """
    global storage, items, current_session

    storage         = DataStorage(data_dir)
    items           = storage.load_items_from_config(config_path)
    current_session = None  # admin creates the session via the UI

    seed_rng()


def bootstrap() -> argparse.Namespace:
    args = parse_args()
    init_app(Path(args.config), Path("data"))
    return args


if __name__ == "__main__":
    atexit.register(cleanup)
    run_args = bootstrap()
    app.run(host=run_args.host, port=run_args.port, debug=False)
