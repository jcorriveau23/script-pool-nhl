LIMIT = 3000
ACTIVE = True

import requests
import logging
from data import players_info
import json 
from pymongo import MongoClient
from dataclasses import asdict

URL = f"https://search.d3.nhle.com/api/v1/search/player?culture=en-us&limit={LIMIT}&q=*&active={ACTIVE}"

active_players = json.loads(requests.get(URL).text)
def _get_position_code(position: str) -> players_info.Position:
    match position:
        case "R" | "L" | "C":
            return "F"
        case "D":
            return "D"
        case "G":
            return "G"
        case None:
            return None
        case _:
            raise ValueError(f"The position {position} was not expected.")


def _player_info_changed(database_player: dict, nhl_player: dict)->bool:
    database_team_id = database_player.get("team")
    new_team_id = nhl_player.get("teamId")
    return database_player["active"] != nhl_player["active"] or (str(database_team_id) if database_team_id is not None else None) != new_team_id

def get_active_players() -> None:
    active_players = json.loads(requests.get(URL).text)

    mongo_client = MongoClient()
    db = mongo_client.hockeypool
    players_collection = db.players

    logging.warning(f"{len(active_players)} players found.")

    players_not_updated = 0
    players_updated_in_database = 0 

    for nhl_player in active_players:
        player_id = int(nhl_player["playerId"])
        team_id = nhl_player.get("teamId")

        results = players_collection.find({'id': player_id})
        players = [doc for doc in results]

        if len(players) == 0:
            stored_player_info = players_info.PlayerInfo(
                id=player_id,
                active=nhl_player["active"],
                name=nhl_player["name"],
                team=int(team_id) if team_id is not None else None,
                position=_get_position_code(nhl_player["positionCode"]),
                age=None,
                salary_cap=None,
                contract_expiration_season=None,
                game_played=None,
                goals=None,
                assists=None,
                points=None,
                points_per_game=None,
                goal_against_average=None,
                save_percentage=None,
            )
            logging.warning(f"Added {stored_player_info.name} to the database.")
        elif _player_info_changed(players[0], nhl_player):
            stored_player_info = players_info.PlayerInfo(
                id=player_id,
                active=nhl_player["active"],
                name=nhl_player["name"],
                team=int(team_id) if team_id is not None else None,
                position=_get_position_code(nhl_player["positionCode"]),
                age=players[0].get("age"),
                salary_cap=players[0].get("salary_cap"),
                contract_expiration_season=players[0].get("contract_expiration_season"),
                game_played=players[0].get("game_played"),
                goals=players[0].get("goals"),
                assists=players[0].get("assists"),
                points=players[0].get("points"),
                points_per_game=players[0].get("points_per_game"),
                goal_against_average=players[0].get("goal_against_average"),
                save_percentage=players[0].get("save_percentage"),
            )
            logging.warning(f"{nhl_player["name"]} info updated.")
        else:
            players_not_updated += 1
            continue

        players_updated_in_database += 1
        players_collection.update_one({'id': player_id}, {'$set': asdict(stored_player_info)}, upsert=True)
    
    logging.warning(f"{players_updated_in_database} updated and {players_not_updated} already in database.")


if __name__ == "__main__":
    get_active_players()