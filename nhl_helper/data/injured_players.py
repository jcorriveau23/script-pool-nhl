from pydantic import BaseModel


class InjuredPlayerInfo(BaseModel):
   name: str
   position: str
   date: str
   type: str
   recovery: str

class MongoInjuredPlayerInfo(InjuredPlayerInfo):
    """
    A document read straight out of MongoDB.

    Mongo's `_id` is simply dropped: pydantic ignores unknown keys on input, so
    it never reaches `model_dump()` and therefore never lands in a `$set`, which
    MongoDB would reject as an attempt to modify an immutable field.
    """
