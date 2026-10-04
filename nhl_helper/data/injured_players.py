from pydantic import BaseModel


class InjuredPlayerInfo(BaseModel):
   name: str
   position: str
   date: str
   type: str
   recovery: str
   # The NHL team id the player is under contract to, from the players
   # collection. Written into the file so the frontend's injury report does not
   # have to resolve every player's team against the NHL API. `None` for a
   # player with no current team, such as an unsigned free agent.
   team: int | None = None

class MongoInjuredPlayerInfo(InjuredPlayerInfo):
    """
    A document read straight out of MongoDB.

    Mongo's `_id` is simply dropped: pydantic ignores unknown keys on input, so
    it never reaches `model_dump()` and therefore never lands in a `$set`, which
    MongoDB would reject as an attempt to modify an immutable field.
    """
