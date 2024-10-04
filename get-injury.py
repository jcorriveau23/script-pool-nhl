# This script fetch the current players injured in the nhl store it in a dictionnary and paste it in a static file inside the public folder.

import json
from pymongo import MongoClient
import requests
import logging
from bs4 import BeautifulSoup
from data.injured_players import InjuredPlayerInfo
from utils.find_players import find_player_in_database_with_name

API_URL = 'https://www.cbssports.com/nhl/injuries/'

def fetch_injured_players_cbs() -> tuple[dict[int, InjuredPlayerInfo], dict[str, int | None]]:
    mongo_client = MongoClient()
    db = mongo_client.hockeypool
    players_collection = db.players
    dupplicate_names_players: list[str] = []
    non_matching_players: dict[str, int | None] = {}

    injured_players: dict[str, InjuredPlayerInfo] = {}

    response = requests.request('GET', API_URL)
    data = BeautifulSoup(response.text, 'lxml')
    for row in data.find_all("table"):
        # print(row)
        players = row.tbody.find_all("tr")
        for player in players:
            tds = player.find_all("td")

            player_name: str = player.find_all("a")[1].text.strip()
            logging.info(f"{player_name} is currently injured.")
            first_name, last_name = player_name.split(" ")

            player_found = find_player_in_database_with_name(players_collection, first_name, last_name, True, dupplicate_names_players)

            if player_found is not None:
                injured_players[player_found.id] = InjuredPlayerInfo(
                    name=player_name,
                    position=tds[1].text.strip(),
                    date=tds[2].text.strip(),
                    type=tds[3].text.strip(),
                    recovery=tds[4].text.strip(),
                )
            else:
                logging.warning(f"{player_name} was not found in database.")
                non_matching_players[player_name] = None
    
    return injured_players, non_matching_players

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    injured_players, non_matching_players = fetch_injured_players_cbs()

    # Convert the dataclass instances to dictionaries
    serializable_data = {key: value.model_dump() for key, value in injured_players.items()}

    # Dump the dictionary to a JSON file
    with open(r'/home/jcorriveau/Documents/dev/shad-cn-frontend-pool-nhl/frontend-pool-nhl/public/injured-players.json', 'w') as json_file:
        json.dump(serializable_data, json_file, indent=4)

    with open('non-matching-players-cbs.json', 'w') as json_file:
        json.dump(non_matching_players, json_file, indent=4)