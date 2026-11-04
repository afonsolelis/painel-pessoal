from datetime import UTC, datetime
from decimal import Decimal

from pipeline.f1data import parse_driver_standings, parse_races

RACES = {
    "RaceTable": {
        "Races": [
            {
                "season": "2026",
                "round": "21",
                "raceName": "Brazilian Grand Prix",
                "url": "https://en.wikipedia.org/wiki/2026_S%C3%A3o_Paulo_Grand_Prix",
                "date": "2026-11-08",
                "time": "17:00:00Z",
                "Circuit": {
                    "circuitId": "interlagos",
                    "circuitName": "Autódromo José Carlos Pace",
                    "Location": {"locality": "São Paulo", "country": "Brazil"},
                },
                "Qualifying": {"date": "2026-11-07", "time": "18:00:00Z"},
            }
        ]
    }
}

DRIVERS = {
    "StandingsTable": {
        "StandingsLists": [
            {
                "season": "2026",
                "round": "20",
                "DriverStandings": [
                    {
                        "position": "1",
                        "points": "380.5",
                        "wins": "8",
                        "Driver": {
                            "driverId": "antonelli",
                            "code": "ANT",
                            "permanentNumber": "12",
                            "givenName": "Andrea Kimi",
                            "familyName": "Antonelli",
                            "nationality": "Italian",
                        },
                        "Constructors": [{"constructorId": "mercedes", "name": "Mercedes"}],
                    },
                    {
                        "positionText": "-",
                        "points": "0",
                        "wins": "0",
                        "Driver": {"driverId": "reserve", "givenName": "Res", "familyName": "Erve"},
                        "Constructors": [],
                    },
                ],
            }
        ]
    }
}


def test_parse_races():
    race = parse_races(RACES)[0]
    assert race.circuit_id == "interlagos"
    assert race.race_start == datetime(2026, 11, 8, 17, tzinfo=UTC)
    assert race.sprint_start is None


def test_parse_driver_standings_handles_missing_position():
    leader, reserve = parse_driver_standings(DRIVERS)
    assert leader.points == Decimal("380.5") and leader.constructor_name == "Mercedes"
    assert reserve.position is None and reserve.constructor_name is None


def test_empty_standings():
    assert parse_driver_standings({"StandingsTable": {"StandingsLists": []}}) == []
