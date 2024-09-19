# This script fetch the current players injured in the nhl store it in a dictionnary and paste it in a static file inside the public folder.

from dataclasses import asdict
import json
import requests
import logging
from bs4 import BeautifulSoup
from data.injured_players import InjuredPlayerInfo

API_URL = 'https://www.cbssports.com/nhl/injuries/'

def fetch_injured_players_cbs() -> dict[str, InjuredPlayerInfo]:
    try:
        injured_players: dict[str, InjuredPlayerInfo] = {}

        response = requests.request('GET', API_URL)
        data = BeautifulSoup(response.text, 'lxml')
        for row in data.find_all("table"):
            # print(row)
            players = row.tbody.find_all("tr")
            for player in players:
                tds = player.find_all("td")

                injured_players[player.find_all("a")[1].text] = InjuredPlayerInfo(
                    position=tds[1].text.strip(),
                    date=tds[2].text.strip(),
                    type=tds[3].text.strip(),
                    recovery=tds[4].text.strip(),
                )
        
        return injured_players

    except Exception as e:
        logging.error(e)

if __name__ == "__main__":
    injured_players = fetch_injured_players_cbs()

    # Convert the dataclass instances to dictionaries
    serializable_data = {key: asdict(value) for key, value in injured_players.items()}

    # Dump the dictionary to a JSON file
    with open('injured_players.json', 'w') as json_file:
        json.dump(serializable_data, json_file, indent=4)