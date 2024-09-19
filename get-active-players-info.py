from dataclasses import asdict
import logging
from typing import Any
import json
import requests
from bs4 import BeautifulSoup

from data.players_info import MongoPlayerInfo, PlayerInfo
from pymongo import MongoClient

LIMIT = 3000
PUCK_PEDIA_URL = f"https://dashboard.puckpedia.com/?sz={LIMIT}"

with open("non-matching-players.json", "r") as json_file:
    EXCEPTION_PLAYERS: dict[str, int | None] = json.loads(json_file.read())

def _fill_last_season_score(database_player_found: PlayerInfo, cells: Any) -> None:
    """
    Return all the score from puck pedia into the LastSeasonScore in database.
    """

    def _get_optional_int_value(string_integer: str)->int | None:
        try:
            return int(string_integer)
        except ValueError:
            return None
        
    def _get_optional_float_value(string_integer: str)->float | None:
        try:
            return float(string_integer)
        except ValueError:
            return None
        
    game_played = _get_optional_int_value(cells[20].text)
    points = _get_optional_int_value(cells[23].text)

    database_player_found.game_played = game_played
    database_player_found.goals = _get_optional_int_value(cells[21].text)
    database_player_found.assists = _get_optional_int_value(cells[22].text)
    database_player_found.points = points
    database_player_found.points_per_game = points / game_played if game_played is not None and game_played > 0 and points is not None else None
    database_player_found.goal_against_average = _get_optional_float_value(cells[28].text)
    database_player_found.save_percentage = _get_optional_float_value(cells[29].text)

def _get_converted_season(formated_season: str)->int | None:
    """
    Return a season as integer to store in data base.
    (i.e., "2024-25" -> 20242025)
    """

    if formated_season == "2023-24":
        return None
    
    return int(formated_season[:4]+"20"+formated_season[5:])

def _get_player_name(puck_pedia_player_name: str)-> tuple[str, str] | None:
    """
    Convert puck pedia player name into last name and from name.
    """
    splitted_name: list[str] = puck_pedia_player_name.split(", ")

    if len(splitted_name) != 2:
        logging.warning(f"Invalid name, could not recover a first and last name from '{puck_pedia_player_name}', this player will be ignored.")
        return None

    return splitted_name[1], splitted_name[0]



def find_player_in_database_with_name(players_collection: Any, first_name: str, last_name: str, active: bool, non_matching_players: dict[str, int | None], dupplicate_names_players: list[str]) -> PlayerInfo | None:
    player_name = f"{first_name} {last_name}"
    query = {"name": {"$regex": player_name, "$options": "i"}, "active": active} 

    results = players_collection.find(query)
    players = [MongoPlayerInfo(**doc) for doc in results]

    match len(players):
        case 1:
            if player_name in non_matching_players:
                non_matching_players.pop(player_name)
            return players[0]
        case 0:
            # Try to find player only with last name.
            query = {"name": {"$regex": last_name, "$options": "i"}, "active": active} 
            results = players_collection.find(query)
            players = [MongoPlayerInfo(**doc) for doc in results]

            if len(players) == 1:
                if player_name in non_matching_players:
                    non_matching_players.pop(player_name)
                return players[0]
            
            logging.warning(f"No player found with name '{player_name}', please update the player information manually.")

            non_matching_players[player_name] = None
            return None
        case _:
            logging.warning(f"{len(players)} players found with with name '{player_name}', please update the player information manually.")

            dupplicate_names_players.append(player_name)
            return None

def find_player_in_database_with_id(players_collection: Any, player_id: int) -> PlayerInfo:
    query = {"id": player_id} 

    results = players_collection.find(query)
    players = [MongoPlayerInfo(**doc) for doc in results]

    if len(players) != 1:
        raise ValueError(f"only one players should have been found with id {player_id}.")
    
    return players[0]

def update_player_in_database(players_collection: Any, database_player_found: PlayerInfo, cells: Any, contract_expiration_season: int | None) -> bool:
    database_player_found.age = int(cells[7].text)
    database_player_found.contract_expiration_season = contract_expiration_season
    database_player_found.salary_cap = _get_salary_cap(cells[3].text) if contract_expiration_season is not None else None
    _fill_last_season_score(database_player_found, cells)

    players_collection.update_one({'id': database_player_found.id}, {'$set': asdict(database_player_found)}, upsert=True)

def _get_salary_cap(formated_salary: str) -> float | None:
    try:
        return float(formated_salary.replace("$", "").replace(",", ""))
    except ValueError:
        logging.warning(f"Cannot convert {formated_salary} in a float dollar amount.")
        return None


def get_puck_pedia_player_info()->PlayerInfo:
    # Make sure you have a connection to the players documents in database.
    mongo_client = MongoClient()
    db = mongo_client.hockeypool
    players_collection = db.players
        
    # Request and parse the HTML to recover player information.
    with open(r"puckpedia.html") as file:
        html_text = file.read()
    # html_text = requests.get(PUCK_PEDIA_URL).text
    soup = BeautifulSoup(html_text, 'html.parser')

    table = soup.find("table")

    non_matching_players: dict[str, int | None] = {}
    dupplicate_names_players: list[str] = []

    # Parse all rows except header
    for row in table.findAll("tr")[1:]:
        cells = row.findAll("td")

        player_name = _get_player_name(cells[1].text)
        print(player_name)

        match player_name:
            case None:
                logging.warning(f"{player_name} does not have a valid name, please update the player information manually.")
                non_matching_players[player_name] = None
                continue
            case tuple():
                first_name, last_name = player_name
                contract_expiration_season = _get_converted_season(cells[18].text)

                key_player_name = f"{first_name} {last_name}"

                logging.info(f"{key_player_name} (current contract end season '{contract_expiration_season}')")

                if contract_expiration_season is None:
                    logging.warning(f"{key_player_name} have no contract for the beginning of the 2024-25 season")

                if EXCEPTION_PLAYERS.get(key_player_name) is not None:
                    database_player_found = find_player_in_database_with_id(players_collection, EXCEPTION_PLAYERS[key_player_name])
                    update_player_in_database(players_collection, database_player_found, cells, contract_expiration_season)
                    non_matching_players[key_player_name] = EXCEPTION_PLAYERS[key_player_name]
                else:
                    # Try to find in active players first
                    database_player_found = find_player_in_database_with_name(players_collection, first_name, last_name, False, non_matching_players, dupplicate_names_players)
                    if database_player_found is not None:
                        update_player_in_database(players_collection, database_player_found, cells, contract_expiration_season)
                    else:
                        # Try to find in inactive players as well
                        database_player_found = find_player_in_database_with_name(players_collection, first_name, last_name, True, non_matching_players, dupplicate_names_players)
                        if database_player_found is not None:
                            update_player_in_database(players_collection, database_player_found, cells, contract_expiration_season)

    logging.warning(f"A total of {len(list(player_name for player_name, player_id in non_matching_players.items() if player_id is None))} was not able to be match")
    with open("non-matching-players.json", "w") as json_file:
        json.dump(non_matching_players, json_file, indent=4) 



if __name__ == "__main__":             
    get_puck_pedia_player_info()







