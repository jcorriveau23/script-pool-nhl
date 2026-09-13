from enum import StrEnum

from pydantic import BaseModel


class Position(StrEnum):
    F = "F"
    D = "D"
    G = "G"


class PlayerInfo(BaseModel):
    id: int
    active: bool
    name: str
    team: int | None
    position: Position | None
    age: int | None
    salary_cap: float | None

    # Including the selected season (i.e., if 20232024 is stored, the contract is valid for the 2023-24 season)
    contract_expiration_season: int | None

    # stats
    game_played: int | None
    goals: int | None
    assists: int | None
    points: int | None
    points_per_game: float | None
    goal_against_average: float | None
    save_percentage: float | None
    saves: int | None
    shots: int | None
    wins: int | None
    ot: int | None


class MongoPlayerInfo(PlayerInfo):
    """
    A document read straight out of MongoDB.

    Mongo's `_id` is simply dropped: pydantic ignores unknown keys on input, so
    it never reaches `model_dump()` and therefore never lands in a `$set`, which
    MongoDB would reject as an attempt to modify an immutable field.
    """
