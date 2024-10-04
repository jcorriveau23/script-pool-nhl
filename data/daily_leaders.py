from enum import Enum, StrEnum

from bson import ObjectId
from pydantic import BaseModel

class Decision(StrEnum):
   W = "W"
   L = "L"
   O = "O"

class SkaterStats(BaseModel):
   goals: int
   assists: int
   shootoutGoals: int

class GoalieStats(BaseModel):
   goals: int
   assists: int
   savePercentage: float
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
    _id: ObjectId


class GameType(Enum):
   PRE_SEASON = 1
   REGULAR = 2
