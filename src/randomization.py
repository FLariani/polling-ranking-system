"""
Shuffles items into a random order before showing them to each voter.
Randomising the display order prevents position bias — voters shouldn't always
see the same item at the top of the list.
"""

import random
import time
from typing import List

from models import Item


# Guards against seeding more than once. Re-seeding mid-run would reset the
# random sequence and make shuffles less unpredictable.
_seeded = False


def seed_rng() -> None:
    """Seed the RNG once at startup using the current time.

    Time-based seeding means every app launch gets a different shuffle sequence.
    The guard flag means calling this twice is safe — the second call does nothing.
    """
    global _seeded
    if not _seeded:
        random.seed(int(time.time()))
        _seeded = True


def shuffled_items(items: List[Item]) -> List[Item]:
    """Return a shuffled copy of items without modifying the original list.

    We copy first because random.shuffle works in-place — mutating the main
    items list would break any code that expects a stable order.
    """
    if len(items) < 2 or len(items) > 50:
        raise ValueError("Item list must contain between 2 and 50 items.")

    copy_items = list(items)  # copy so the original list is untouched
    random.shuffle(copy_items)
    return copy_items
