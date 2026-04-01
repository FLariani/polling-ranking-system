from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Item:
    id: int
    item_name: str
    category: str = "default"


@dataclass
class Vote:
    voter_name: str
    item_id: int
    rank: int
    timestamp: datetime


@dataclass(frozen=True)
class Voter:
    id: int
    name: str
    email: str
    timestamp: datetime
