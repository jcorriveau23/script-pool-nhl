import logging
import re
from typing import Any

from nhl_helper.data.players_info import MongoPlayerInfo


def find_player_in_database_with_id(players_collection: Any, player_id: int) -> MongoPlayerInfo:
    query = {"id": player_id}

    results = players_collection.find(query)
    players = [MongoPlayerInfo(**doc) for doc in results]

    if len(players) == 0:
        raise ValueError(f"No player found with id '{player_id}'.")

    if len(players) != 1:
        raise ValueError(f"Only one player should have been found with id '{player_id}'.")

    return players[0]


def build_name_query(pattern: str, active: bool | None) -> dict[str, Any]:
    """
    Build a case-insensitive name query.

    The pattern is escaped by the caller; `active` is only constrained when the
    caller actually asked for it, since `{"active": None}` matches nothing.
    """
    query: dict[str, Any] = {"name": {"$regex": pattern, "$options": "i"}}
    if active is not None:
        query["active"] = active

    return query


def find_player_in_database_with_name(
    players_collection: Any,
    first_name: str,
    last_name: str,
    active: bool | None,
    dupplicate_names_players: list[str],
) -> MongoPlayerInfo | None:
    player_name = f"{first_name} {last_name}"

    # Names come from scraped pages and can contain regex metacharacters
    # (e.g. "T.J. Brodie"), so they must be escaped before being used as a pattern.
    query = build_name_query(re.escape(player_name), active)

    results = players_collection.find(query)
    players = [MongoPlayerInfo(**doc) for doc in results]

    match len(players):
        case 1:
            return players[0]
        case 0:
            # Try to find player that ends with last name.
            query = build_name_query(re.escape(last_name) + "$", active)
            results = players_collection.find(query)
            players = [MongoPlayerInfo(**doc) for doc in results]

            if len(players) == 1:
                return players[0]

            logging.debug(f"No player found with name '{player_name}', please update the player information manually.")
            return None
        case _:
            logging.debug(
                f"{len(players)} players found with with name '{player_name}', please update the player information manually."
            )

            dupplicate_names_players.append(player_name)
            return None
