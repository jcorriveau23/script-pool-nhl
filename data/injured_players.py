from dataclasses import dataclass
from enum import StrEnum

from bson import ObjectId


@dataclass
class InjuredPlayerInfo:
   position: str
   date: str
   type: str
   recovery: str

@dataclass
class MongoInjuredPlayerInfo(InjuredPlayerInfo):
    _id: ObjectId
