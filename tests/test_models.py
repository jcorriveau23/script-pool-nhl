"""
Regression tests for the `_id` leak: a document read from MongoDB must never
carry `_id` back into a `$set`, which MongoDB rejects as an immutable field.
"""

from bson import ObjectId

from nhl_helper.data.daily_leaders import MongoDailyLeaders
from nhl_helper.data.players_info import MongoPlayerInfo, Position


def player_document() -> dict:
    return {
        "_id": ObjectId(),
        "id": 8478402,
        "active": True,
        "name": "Connor McDavid",
        "team": 22,
        "position": "F",
        "age": 28,
        "salary_cap": 12500000.0,
        "contract_expiration_season": 20252026,
        "game_played": 10,
        "goals": 5,
        "assists": 12,
        "points": 17,
        "points_per_game": 1.7,
        "goal_against_average": None,
        "save_percentage": None,
        "saves": None,
        "shots": None,
        "wins": None,
        "ot": None,
    }


def test_mongo_player_info_drops_id_from_model_dump():
    player = MongoPlayerInfo(**player_document())

    assert "_id" not in player.model_dump()
    assert player.id == 8478402
    assert player.position is Position.F


def test_mongo_daily_leaders_drops_id_from_model_dump():
    leaders = MongoDailyLeaders(
        **{"_id": ObjectId(), "date": "2025-10-08", "skaters": [], "goalies": [], "played": []}
    )

    assert "_id" not in leaders.model_dump()
    assert leaders.date == "2025-10-08"


def test_position_serialises_as_a_plain_string():
    player = MongoPlayerInfo(**player_document())

    # pymongo must receive a str, not an enum wrapper.
    assert player.model_dump()["position"] == "F"
    assert isinstance(player.model_dump()["position"], str)
