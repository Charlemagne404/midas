"""Append-only compressed research journal with bounded, queryable decision indexes."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import time
import zlib
from pathlib import Path
from typing import Any

from .research_schema import digest
from .storage import canonical


class Journal:
    def __init__(self, root: Path, *, budget: int, reserve: int) -> None:
        root.mkdir(parents=True, exist_ok=True)
        self.root = root
        self.budget = budget
        self.reserve = reserve
        self.db = sqlite3.connect(root / "shadow.sqlite")
        self.db.execute("pragma journal_mode=WAL")
        self.db.execute("pragma synchronous=FULL")
        self.db.execute("pragma wal_autocheckpoint=1000")
        self.db.executescript("""
        create table if not exists events(seq integer primary key,kind text,occurred_ns integer,body blob,previous_sha text,sha text);
        create trigger if not exists immutable_events_update before update on events begin select raise(abort,'immutable event'); end;
        create trigger if not exists immutable_events_delete before delete on events begin select raise(abort,'immutable event'); end;
        create table if not exists decisions(id text primary key,ns integer,condition text,market_id text,family_id text,day text,source_ordinal integer,event_seq integer,commit_ns integer,unique(condition,source_ordinal));
        create index if not exists decisions_time on decisions(ns);
        create table if not exists outcomes(decision_id text,horizon integer,status text,event_seq integer,primary key(decision_id,horizon));
        create table if not exists observations(ns integer,condition text,event_seq integer,primary key(ns,condition));
        create index if not exists observations_time on observations(ns);
        create table if not exists runtime(key text primary key,body blob,sha text);
        create table if not exists reserves(policy text,decision_id text,condition text,family_id text,amount text,until_ns integer,primary key(policy,decision_id));
        create table if not exists family_map(condition text primary key,family_id text);
        """)
        self.db.commit()

    def check_capacity(self) -> None:
        size = sum(p.stat().st_size for p in self.root.rglob("*") if p.is_file())
        if size + 8 * 1024**2 > self.budget:
            raise ValueError("Shadow evidence budget exhausted; no observations deleted")
        if shutil.disk_usage(self.root).free - 8 * 1024**2 < self.reserve:
            raise ValueError("Shadow free-space reserve breached")

    def append(self, kind: str, body: dict[str, Any], now: int | None = None) -> int:
        previous = self.db.execute("select sha from events order by seq desc limit 1").fetchone()
        prior = previous[0] if previous else "0" * 64
        ns = now if now is not None else time.time_ns()
        encoded = canonical(body)
        sha = digest([prior, kind, ns, hashlib.sha256(encoded).hexdigest()])
        cur = self.db.execute(
            "insert into events(kind,occurred_ns,body,previous_sha,sha) values(?,?,?,?,?)",
            (kind, ns, zlib.compress(encoded), prior, sha),
        )
        if cur.lastrowid is None:
            raise ValueError("Journal insertion failed")
        return cur.lastrowid

    def event(self, seq: int) -> dict[str, Any]:
        row = self.db.execute("select body from events where seq=?", (seq,)).fetchone()
        if row is None:
            raise ValueError("Missing shadow journal event")
        return dict(json.loads(zlib.decompress(row[0])))

    def save_runtime(self, value: dict[str, Any]) -> None:
        data = canonical(value)
        self.db.execute(
            "insert or replace into runtime values('checkpoint',?,?)",
            (zlib.compress(data), hashlib.sha256(data).hexdigest()),
        )

    def runtime(self) -> dict[str, Any] | None:
        row = self.db.execute("select body,sha from runtime where key='checkpoint'").fetchone()
        if row is None:
            return None
        data = zlib.decompress(row[0])
        if hashlib.sha256(data).hexdigest() != row[1]:
            raise ValueError("Shadow runtime checkpoint corruption")
        return dict(json.loads(data))

    def decision(self, row: dict[str, Any], runtime: dict[str, Any]) -> bool:
        if self.db.execute(
            "select 1 from decisions where condition=? and source_ordinal=?",
            (row["condition"], row["decision_ordinal"]),
        ).fetchone():
            return False
        with self.db:
            seq = self.append("decision", row, row["decision_ns"])
            self.db.execute(
                "insert into decisions values(?,?,?,?,?,?,?,?,?)",
                (
                    row["id"],
                    row["decision_ns"],
                    row["condition"],
                    row["market_id"],
                    row["family_id"],
                    row["day_utc"],
                    row["decision_ordinal"],
                    seq,
                    0,
                ),
            )
            for policy in row["policies"]:
                if policy["action"] == "hypothetical_trade":
                    self.db.execute(
                        "insert into reserves values(?,?,?,?,?,?)",
                        (
                            policy["policy"],
                            row["id"],
                            row["condition"],
                            row["family_id"],
                            policy["reserved_capital"],
                            row["decision_ns"] + row["settlement_lock_ns"],
                        ),
                    )
            self.save_runtime(runtime)
        # This timestamp is after the decision has durably committed. Future
        # labels must have source receipts strictly later than this marker.
        committed = time.time_ns()
        with self.db:
            self.append(
                "decision_committed",
                dict(decision_id=row["id"], decision_event_seq=seq, committed_ns=committed),
                committed,
            )
            self.db.execute("update decisions set commit_ns=? where id=?", (committed, row["id"]))
        return True

    def outcome(self, row: dict[str, Any]) -> bool:
        if self.db.execute(
            "select 1 from outcomes where decision_id=? and horizon=?",
            (row["decision_id"], row["horizon_ms"]),
        ).fetchone():
            return False
        with self.db:
            seq = self.append("followup", row)
            self.db.execute(
                "insert into outcomes values(?,?,?,?)",
                (row["decision_id"], row["horizon_ms"], row["labels"]["status"], seq),
            )
        return True

    def pending(self, horizons: list[int]) -> list[dict[str, Any]]:
        result = []
        for seq, commit in self.db.execute(
            "select event_seq,commit_ns from decisions order by ns desc limit 200"
        ):
            row = self.event(seq)
            done = {
                r[0]
                for r in self.db.execute(
                    "select horizon from outcomes where decision_id=?", (row["id"],)
                )
            }
            missing = [h for h in horizons if h not in done]
            if missing:
                result.append(dict(row=row, committed_ns=commit, horizons=missing))
        return result

    def reserves(self, policy: str, now: int) -> list[dict[str, Any]]:
        return [
            dict(condition=r[0], family_id=r[1], amount=r[2])
            for r in self.db.execute(
                "select condition,family_id,amount from reserves where policy=? and until_ns>?",
                (policy, now),
            )
        ]

    def summary(self) -> dict[str, Any]:
        return dict(
            decisions=self.db.execute("select count(*) from decisions").fetchone()[0],
            observations=self.db.execute("select count(*) from observations").fetchone()[0],
            followups=dict(self.db.execute("select status,count(*) from outcomes group by status")),
            markets=self.db.execute("select count(distinct market_id) from decisions").fetchone()[
                0
            ],
            families=self.db.execute(
                "select count(distinct coalesce(f.family_id,d.family_id)) from decisions d left join family_map f on d.condition=f.condition"
            ).fetchone()[0],
            days=[r[0] for r in self.db.execute("select distinct day from decisions order by day")],
            last_decision_ns=self.db.execute("select max(ns) from decisions").fetchone()[0],
            events=self.db.execute("select count(*) from events").fetchone()[0],
        )

    def verify(self) -> dict[str, Any]:
        if self.db.execute("pragma integrity_check").fetchone()[0] != "ok":
            raise ValueError("Shadow SQLite integrity failure")
        prior = "0" * 64
        n = 0
        for seq, kind, ns, compressed, previous, sha in self.db.execute(
            "select * from events order by seq"
        ):
            encoded = zlib.decompress(compressed)
            if (
                seq != n + 1
                or previous != prior
                or digest([prior, kind, ns, hashlib.sha256(encoded).hexdigest()]) != sha
            ):
                raise ValueError("Shadow journal hash-chain corruption")
            prior = sha
            n += 1
        return dict(events=n, tail_sha256=prior, sqlite_integrity="ok")

    def close(self) -> None:
        self.db.close()
