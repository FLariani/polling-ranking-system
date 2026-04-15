"""
Tallies votes and produces a sorted results list.

Keeping this logic separate from storage means it can be tested with
in-memory data — no files needed.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from models import Item, Vote


@dataclass
class ResultRow:
    """Summary for one item after all votes are counted."""

    item_id: int
    item_name: str
    average_rank: float  # lower is better — rank 1 means first choice
    vote_count: int


def filter_votes_by_time(
    votes: Iterable[Vote],
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> List[Vote]:
    """Return only votes whose timestamp falls within the given window.

    Either boundary can be None, which means no limit on that side.
    """
    filtered = []
    for vote in votes:
        if start and vote.timestamp < start:
            continue  # too early
        if end and vote.timestamp > end:
            continue  # too late
        filtered.append(vote)
    return filtered


def calculate_results(items: List[Item], votes: Iterable[Vote]) -> List[ResultRow]:
    """Compute average rank per item and return rows sorted best-first.

    defaultdict(int) initialises missing keys to 0 automatically, so we
    don't need an explicit "if item not seen yet" check on every vote.
    """
    sums: Dict[int, int] = defaultdict(int)    # running total of rank values per item
    counts: Dict[int, int] = defaultdict(int)  # number of votes per item

    for vote in votes:
        sums[vote.item_id] += vote.rank
        counts[vote.item_id] += 1

    rows: List[ResultRow] = []
    for item in items:
        count = counts[item.id]
        avg = (sums[item.id] / count) if count else 0.0  # guard against division by zero
        rows.append(ResultRow(item_id=item.id, item_name=item.item_name, average_rank=avg, vote_count=count))

    # Primary sort: lowest average rank first (best result).
    # Items with no votes use float("inf") so they sink to the bottom.
    # Ties broken by vote count (more votes = higher), then alphabetically.
    rows.sort(key=lambda r: (r.average_rank if r.vote_count else float("inf"), -r.vote_count, r.item_name.lower()))
    return rows
