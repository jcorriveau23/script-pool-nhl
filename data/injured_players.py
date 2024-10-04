from pydantic import BaseModel

from bson import ObjectId


class InjuredPlayerInfo(BaseModel):
   name: str
   position: str
   date: str
   type: str
   recovery: str

class MongoInjuredPlayerInfo(InjuredPlayerInfo):
    _id: ObjectId
