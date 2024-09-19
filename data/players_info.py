from dataclasses import dataclass
from enum import StrEnum

from bson import ObjectId

@dataclass
class Position(StrEnum):
    F = "F",
    D = "D",
    G = "G"

@dataclass
class PlayerInfo:
    id: int
    active: bool
    name: str
    team: int | None
    position: Position | None
    age: int | None
    salary_cap: float | None

    # Including the selected season (i.e., if 20232024 is stored, the contract is valid for the 2023-24 season)
    contract_expiration_season: int | None

    # The score made by the player (returned from puckpedia)
    game_played: int | None
    goals: int | None
    assists: int | None
    points: int | None
    points_per_game: float | None
    goal_against_average: float | None
    save_percentage: float | None

@dataclass
class MongoPlayerInfo(PlayerInfo):
    _id: ObjectId
