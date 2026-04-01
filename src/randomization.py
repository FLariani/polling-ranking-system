import random
import time
from typing import List

from models import Item


_seeded = False


def seed_rng() -> None:
    """Seed RNG once at startup using current time (SDD TR-15/TR-16 intent)."""
    global _seeded
    if not _seeded:
        random.seed(int(time.time()))
        _seeded = True


def shuffled_items(items: List[Item]) -> List[Item]:
    """Return a shuffled copy while preserving the original list."""
    if len(items) < 2 or len(items) > 50:
        raise ValueError("Item list must contain between 2 and 50 items.")

    copy_items = list(items)
    random.shuffle(copy_items)
    return copy_items
