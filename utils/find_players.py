from typing import Any
from data.players_info import MongoPlayerInfo, PlayerInfo
import logging


def find_player_in_database_with_id(players_collection: Any, player_id: int) -> PlayerInfo:
    query = {"id": player_id} 

    results = players_collection.find(query)
    players = [MongoPlayerInfo(**doc) for doc in results]

    if len(players) != 1:
        raise ValueError(f"only one players should have been found with id {player_id}.")
    
    return players[0]




def find_player_in_database_with_name(players_collection: Any, first_name: str, last_name: str, active: bool, dupplicate_names_players: list[str]) -> PlayerInfo | None:
    player_name = f"{first_name} {last_name}"
    query = {"name": {"$regex": player_name, "$options": "i"}, "active": active} 

    results = players_collection.find(query)
    players = [MongoPlayerInfo(**doc) for doc in results]

    match len(players):
        case 1:
            return players[0]
        case 0:
            # Try to find player that ends with last name.
            query = {"name": {"$regex": last_name + "$", "$options": "i"}, "active": active} 
            results = players_collection.find(query)
            players = [MongoPlayerInfo(**doc) for doc in results]

            if len(players) == 1:
                return players[0]
            
            logging.debug(f"No player found with name '{player_name}', please update the player information manually.")
            return None
        case _:
            logging.debug(f"{len(players)} players found with with name '{player_name}', please update the player information manually.")

            dupplicate_names_players.append(player_name)
            return None