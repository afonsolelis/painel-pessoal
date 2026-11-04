"""Dados esportivos (calendário e classificações) via API Jolpica (sucessora da Ergast)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import requests


@dataclass(slots=True)
class Race:
    season: int
    round: int
    race_name: str
    circuit_id: str
    circuit_name: str
    locality: str | None
    country: str | None
    race_start: datetime
    qualifying_start: datetime | None
    sprint_start: datetime | None
    wiki_url: str | None


@dataclass(slots=True)
class DriverStanding:
    season: int
    driver_id: str
    after_round: int
    position: int | None
    driver_code: str | None
    driver_number: str | None
    given_name: str
    family_name: str
    nationality: str | None
    constructor_name: str | None
    points: Decimal
    wins: int


@dataclass(slots=True)
class ConstructorStanding:
    season: int
    constructor_id: str
    after_round: int
    position: int | None
    name: str
    nationality: str | None
    points: Decimal
    wins: int


def _ts(block: dict | None) -> datetime | None:
    if not block or not block.get("date"):
        return None
    time = (block.get("time") or "00:00:00Z").replace("Z", "+00:00")
    return datetime.fromisoformat(f"{block['date']}T{time}").astimezone(UTC)


def _int(value: str | None) -> int | None:
    return int(value) if value and value.isdigit() else None


def _get(session: requests.Session, url: str, timeout: float) -> dict:
    resp = session.get(url, params={"limit": 100}, timeout=timeout, headers={"Accept": "application/json"})
    resp.raise_for_status()
    return resp.json()["MRData"]


def parse_races(payload: dict) -> list[Race]:
    races = []
    for r in payload["RaceTable"]["Races"]:
        circuit, loc = r["Circuit"], r["Circuit"].get("Location", {})
        races.append(
            Race(
                season=int(r["season"]),
                round=int(r["round"]),
                race_name=r["raceName"],
                circuit_id=circuit["circuitId"],
                circuit_name=circuit["circuitName"],
                locality=loc.get("locality"),
                country=loc.get("country"),
                race_start=_ts(r),
                qualifying_start=_ts(r.get("Qualifying")),
                sprint_start=_ts(r.get("Sprint")),
                wiki_url=r.get("url"),
            )
        )
    return races


def parse_driver_standings(payload: dict) -> list[DriverStanding]:
    lists = payload["StandingsTable"]["StandingsLists"]
    if not lists:
        return []
    table = lists[0]
    season, rnd = int(table["season"]), int(table["round"])
    out = []
    for s in table["DriverStandings"]:
        d, teams = s["Driver"], s.get("Constructors") or []
        out.append(
            DriverStanding(
                season=season,
                driver_id=d["driverId"],
                after_round=rnd,
                position=_int(s.get("position")),
                driver_code=d.get("code"),
                driver_number=d.get("permanentNumber"),
                given_name=d["givenName"],
                family_name=d["familyName"],
                nationality=d.get("nationality"),
                constructor_name=teams[-1]["name"] if teams else None,
                points=Decimal(s.get("points", "0")),
                wins=int(s.get("wins", 0)),
            )
        )
    return out


def parse_constructor_standings(payload: dict) -> list[ConstructorStanding]:
    lists = payload["StandingsTable"]["StandingsLists"]
    if not lists:
        return []
    table = lists[0]
    season, rnd = int(table["season"]), int(table["round"])
    return [
        ConstructorStanding(
            season=season,
            constructor_id=s["Constructor"]["constructorId"],
            after_round=rnd,
            position=_int(s.get("position")),
            name=s["Constructor"]["name"],
            nationality=s["Constructor"].get("nationality"),
            points=Decimal(s.get("points", "0")),
            wins=int(s.get("wins", 0)),
        )
        for s in table["ConstructorStandings"]
    ]


def fetch_all(session: requests.Session, base: str, timeout: float):
    races = parse_races(_get(session, f"{base}/current.json", timeout))
    drivers = parse_driver_standings(_get(session, f"{base}/current/driverStandings.json", timeout))
    teams = parse_constructor_standings(_get(session, f"{base}/current/constructorStandings.json", timeout))
    return races, drivers, teams
