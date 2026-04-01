import csv
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from models import Item, Vote

TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S"
MAX_ITEM_NAME = 100
MAX_VOTER_NAME = 50


@dataclass
class SessionInfo:
    session_id: str
    votes_file: Path
    metadata_file: Path
    created_at: datetime
    status: str


class DataStorage:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.session_log = self.base_dir / "sessions_log.txt"

    def load_items_from_config(self, config_path: Path) -> List[Item]:
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        items: List[Item] = []
        with config_path.open("r", encoding="utf-8") as f:
            for line_num, raw in enumerate(f, start=1):
                value = raw.strip()
                if not value:
                    continue
                if len(value) > MAX_ITEM_NAME:
                    raise ValueError(f"Item on line {line_num} exceeds {MAX_ITEM_NAME} characters.")
                items.append(Item(id=len(items) + 1, item_name=value, category="default"))

        if not (2 <= len(items) <= 50):
            raise ValueError("Config must contain between 2 and 50 non-empty item lines.")
        return items

    def create_session(self) -> SessionInfo:
        now = datetime.now()
        session_id = now.strftime("%Y%m%d_%H%M%S")

        suffix = 0
        while True:
            candidate = f"{session_id}_{suffix}" if suffix else session_id
            votes_file = self.base_dir / f"session_{candidate}.txt"
            metadata_file = self.base_dir / f"session_{candidate}_meta.txt"
            if not votes_file.exists() and not metadata_file.exists():
                session_id = candidate
                break
            suffix += 1

        with votes_file.open("w", encoding="utf-8", newline="") as vf:
            writer = csv.writer(vf)
            writer.writerow(["voter_name", "item_id", "rank", "timestamp", "revote"])
            vf.flush()
            os.fsync(vf.fileno())

        with metadata_file.open("w", encoding="utf-8") as mf:
            mf.write(f"session_id={session_id}\n")
            mf.write(f"created_at={now.strftime(TIMESTAMP_FMT)}\n")
            mf.write("status=open\n")
            mf.flush()
            os.fsync(mf.fileno())

        self._append_session_log(session_id, now, "created")
        return SessionInfo(
            session_id=session_id,
            votes_file=votes_file,
            metadata_file=metadata_file,
            created_at=now,
            status="open",
        )

    def set_session_status(self, session: SessionInfo, status: str) -> None:
        if status not in {"open", "closed"}:
            raise ValueError("Invalid session status")
        lines = {
            "session_id": session.session_id,
            "created_at": session.created_at.strftime(TIMESTAMP_FMT),
            "status": status,
        }
        with session.metadata_file.open("w", encoding="utf-8") as mf:
            for key, value in lines.items():
                mf.write(f"{key}={value}\n")
            mf.flush()
            os.fsync(mf.fileno())
        session.status = status
        self._append_session_log(session.session_id, datetime.now(), f"status:{status}")

    def read_session_status(self, session: SessionInfo) -> str:
        values = self._read_metadata_map(session.metadata_file)
        return values.get("status", "open")

    def save_vote_set(self, session: SessionInfo, voter_name: str, ranked_item_ids: List[int]) -> bool:
        if self.read_session_status(session) == "closed":
            raise RuntimeError("Session is closed; voting and revoting are disabled.")

        safe_name = (voter_name.strip() or "Anonymous")[:MAX_VOTER_NAME]
        now = datetime.now()
        now_s = now.strftime(TIMESTAMP_FMT)

        existing_rows = self._read_vote_rows(session.votes_file)
        had_previous_vote = any(r["voter_name"] == safe_name for r in existing_rows)

        existing_rows = [r for r in existing_rows if r["voter_name"] != safe_name]
        for rank, item_id in enumerate(ranked_item_ids, start=1):
            existing_rows.append(
                {
                    "voter_name": safe_name,
                    "item_id": str(item_id),
                    "rank": str(rank),
                    "timestamp": now_s,
                    "revote": "yes" if had_previous_vote else "no",
                }
            )

        self._write_vote_rows_atomic(session.votes_file, existing_rows)
        if had_previous_vote:
            self._append_session_log(session.session_id, now, f"revote:{safe_name}")
        return had_previous_vote

    def load_votes(self, session: SessionInfo) -> List[Vote]:
        rows = self._read_vote_rows(session.votes_file)
        out: List[Vote] = []
        for r in rows:
            out.append(
                Vote(
                    voter_name=r["voter_name"],
                    item_id=int(r["item_id"]),
                    rank=int(r["rank"]),
                    timestamp=datetime.strptime(r["timestamp"], TIMESTAMP_FMT),
                )
            )
        return out

    def export_results(self, out_file: Path, rows: List[Dict[str, str]]) -> None:
        if out_file.suffix.lower() != ".txt":
            raise ValueError("Results export file must use .txt extension.")

        out_file.parent.mkdir(parents=True, exist_ok=True)
        with out_file.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["item_name", "average_rank", "vote_count"])
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
            f.flush()
            os.fsync(f.fileno())

    def _append_session_log(self, session_id: str, when: datetime, event: str) -> None:
        with self.session_log.open("a", encoding="utf-8") as log:
            log.write(f"{when.strftime(TIMESTAMP_FMT)},{session_id},{event}\n")
            log.flush()
            os.fsync(log.fileno())

    def _read_metadata_map(self, meta_file: Path) -> Dict[str, str]:
        values: Dict[str, str] = {}
        if not meta_file.exists():
            return values
        with meta_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key] = value
        return values

    def _read_vote_rows(self, votes_file: Path) -> List[Dict[str, str]]:
        if not votes_file.exists():
            return []
        with votes_file.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            return list(reader)

    def _write_vote_rows_atomic(self, votes_file: Path, rows: List[Dict[str, str]]) -> None:
        tmp = votes_file.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["voter_name", "item_id", "rank", "timestamp", "revote"],
            )
            writer.writeheader()
            writer.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, votes_file)
