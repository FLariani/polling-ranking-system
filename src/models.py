"""Plain data containers used across the app. No logic lives here."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Item:
    """A single option voters can rank. Frozen so nothing mutates it after load."""

    id: int             # assigned in load order (1, 2, 3 …)
    item_name: str      # label shown on the ballot
    category: str = "default"


@dataclass
class Vote:
    """One rank assignment from one voter for one item."""

    voter_name: str
    item_id: int        # references Item.id
    rank: int           # 1 = top choice; higher = lower preference
    timestamp: datetime  # used when filtering results by time window


@dataclass(frozen=True)
class Voter:
    """A registered voter's identity record. Frozen for the same reason as Item."""

    id: int
    name: str
    email: str
    timestamp: datetime
