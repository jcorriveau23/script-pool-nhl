from enum import Enum, StrEnum

from pydantic import BaseModel


class Decision(StrEnum):
   W = "W"
   L = "L"
   O = "O"  # noqa: E741 - NHL decision code for an overtime loss.

class SkaterStats(BaseModel):
   goals: int
   assists: int
   shootoutGoals: int

class GoalieStats(BaseModel):
   goals: int
   assists: int
   shots: int
   saves: int
   savePercentage: float
   starter: bool
   decision: Decision | None

class SkatersDailyStats(BaseModel):
   id: int
   name: str
   team: int
   stats: SkaterStats
   
class GoalieDailyStats(BaseModel):
   id: int
   name: str
   team: int
   stats: GoalieStats

class DailyLeaders(BaseModel):
   date: str
   skaters: list[SkatersDailyStats]
   goalies: list[GoalieDailyStats]
   played: list[int]


class MongoDailyLeaders(DailyLeaders):
    """
    A document read straight out of MongoDB.

    Mongo's `_id` is simply dropped: pydantic ignores unknown keys on input, so
    it never reaches `model_dump()` and therefore never lands in a `$set`, which
    MongoDB would reject as an attempt to modify an immutable field.
    """


class GameType(Enum):
   PRE_SEASON = 1
   REGULAR = 2
