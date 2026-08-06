from dataclasses import asdict
import logging
from pymongo import MongoClient
import requests
import json
from bs4 import BeautifulSoup

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils import find_players

def season_id(end_year: int) -> int:
    """
    Return the season 
    """
    if end_year <= 0:
        return 0
    
    start = end_year - 1
    return int(f"20{start}20{end_year}")

def fetch_active_players(url="https://capwages.com/players/active"):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.1; Trident/6.0)"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()


    soup = BeautifulSoup(response.text, "html.parser")
    # Extract JSON from the script tag
    script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
    data = json.loads(script_tag.string)

    # Access playersArray
    players = data["props"]["pageProps"]["playersArray"]

    mongo_client = MongoClient()
    db = mongo_client.hockeypool
    players_collection = db.players
    dupplicate_names_players = []
    not_found_players = []

    logging.basicConfig(level=logging.INFO)

    logging.info(f"Found {len(players)} active players with contract information from Capwages.")

    for player in players:
        player_name = player[0].strip()
        if "," in player_name:
            last_name, first_name = player_name.split(", ")
        else:
            first_name, last_name = player_name.split(" ")

        player_db = find_players.find_player_in_database_with_name(players_collection, first_name, last_name, True, dupplicate_names_players)

        if player_db is None:
            player_db = find_players.find_player_in_database_with_name(players_collection, first_name, last_name, False, dupplicate_names_players)
            if player_db is None:
                not_found_players.append(f"{first_name} {last_name}")
                logging.warning(f"No player found with name '{first_name} {last_name}'")
                continue
            else:
                logging.warning(f"Inactive player '{first_name} {last_name}'")


        # 0 = name
        # 1 = N/A
        # 2 = team
        # 3 = position
        # 4 = side
        # 5 weight (pounds)
        # 6 height (inches)
        # 7 country
        # 8 age
        # 9 = game number
        # 10 = goals
        # 11 assists
        # 12 points
        # 13 = N/A
        # 14 = N/A
        # 15 = contract lenght
        # 16 = N/A
        # 17 = N/A
        # 18 = cap hit in hundred of thousand of dollars
        # 19 = base salary
        # 20 = bonus
        # 21 = perf bonus
        # 22 = AAV
        # 23 = N/A
        # 24 = expiration type
        # 25 = age signed
        # 26 = signed by
        # 27 = sign. status
        # 28 = signed age
        # 29 = expiration year

        player_db.age = int(player[8])
        player_db.salary_cap = float(player[18]) * 100000
        player_db.contract_expiration_season = season_id(int(player[29]))

        players_collection.update_one({'id': player_db.id}, {'$set': asdict(player_db)}, upsert=True)

    logging.info(f"Not found players {len(not_found_players)}")
    logging.info(f"dupplicate name players {len(dupplicate_names_players)}")

if __name__ == "__main__":
    players_info = fetch_active_players()