from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from models import Item, Vote


@dataclass
class ResultRow:
    item_id: int
    item_name: str
    average_rank: float
    vote_count: int


def filter_votes_by_time(
    votes: Iterable[Vote],
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> List[Vote]:
    filtered = []
    for vote in votes:
        if start and vote.timestamp < start:
            continue
        if end and vote.timestamp > end:
            continue
        filtered.append(vote)
    return filtered


def calculate_results(items: List[Item], votes: Iterable[Vote]) -> List[ResultRow]:
    sums: Dict[int, int] = defaultdict(int)
    counts: Dict[int, int] = defaultdict(int)

    for vote in votes:
        sums[vote.item_id] += vote.rank
        counts[vote.item_id] += 1

    rows: List[ResultRow] = []
    for item in items:
        count = counts[item.id]
        avg = (sums[item.id] / count) if count else 0.0
        rows.append(
            ResultRow(
                item_id=item.id,
                item_name=item.item_name,
                average_rank=avg,
                vote_count=count,
            )
        )

    # Clarified interpretation: smaller average rank means better ranking (1 is best).
    rows.sort(key=lambda r: (r.average_rank if r.vote_count else float("inf"), -r.vote_count, r.item_name.lower()))
    return rows
