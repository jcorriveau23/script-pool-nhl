import json
import logging

import requests
from bs4 import BeautifulSoup, Tag

from nhl_helper.config import get_settings
from nhl_helper.db import get_database
from nhl_helper.utils import find_players

# Column offsets into a Capwages player row. The full row is:
# 0 name, 1 N/A, 2 team, 3 position, 4 side, 5 weight (lb), 6 height (in),
# 7 country, 8 age, 9 games, 10 goals, 11 assists, 12 points, 13-14 N/A,
# 15 contract length, 16-17 N/A, 18 cap hit (hundreds of thousands),
# 19 base salary, 20 bonus, 21 perf bonus, 22 AAV, 23 N/A, 24 expiration type,
# 25 age signed, 26 signed by, 27 sign. status, 28 signed age, 29 expiration year.
COL_NAME = 0
COL_AGE = 8
COL_CAP_HIT = 18
COL_EXPIRATION_YEAR = 29

CAP_HIT_UNIT = 100000


def season_id(end_year: int) -> int:
    """
    Turn a two-digit contract expiration year into a season id (26 -> 20252026).
    """
    if end_year <= 0:
        return 0

    start = end_year - 1
    return int(f"20{start:02d}20{end_year:02d}")


def split_player_name(player_name: str) -> tuple[str, str]:
    """
    Capwages writes names either as "Last, First" or "First Last".
    """
    player_name = player_name.strip()
    if "," in player_name:
        last_name, first_name = player_name.split(", ", 1)
    else:
        first_name, last_name = player_name.split(" ", 1)

    return first_name, last_name


def parse_players_array(html: str) -> list[list]:
    """
    Pull the Next.js payload out of the Capwages page.
    """
    soup = BeautifulSoup(html, "html.parser")
    script_tag = soup.find("script", {"id": "__NEXT_DATA__"})

    if not isinstance(script_tag, Tag):
        raise RuntimeError("No __NEXT_DATA__ script on the Capwages page; the layout has probably changed.")

    data = json.loads(script_tag.get_text())
    return data["props"]["pageProps"]["playersArray"]


def fetch_active_players(url: str | None = None) -> None:
    settings = get_settings()
    headers = {"User-Agent": "Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.1; Trident/6.0)"}

    response = requests.get(
        url or settings.capwages_url, headers=headers, timeout=settings.request_timeout_seconds
    )
    response.raise_for_status()

    players = parse_players_array(response.text)

    players_collection = get_database().players
    dupplicate_names_players: list[str] = []
    not_found_players: list[str] = []

    logging.info(f"Found {len(players)} active players with contract information from Capwages.")

    for player in players:
        first_name, last_name = split_player_name(player[COL_NAME])

        player_db = find_players.find_player_in_database_with_name(
            players_collection, first_name, last_name, True, dupplicate_names_players
        )

        if player_db is None:
            player_db = find_players.find_player_in_database_with_name(
                players_collection, first_name, last_name, False, dupplicate_names_players
            )
            if player_db is None:
                not_found_players.append(f"{first_name} {last_name}")
                logging.warning(f"No player found with name '{first_name} {last_name}'")
                continue
            else:
                logging.warning(f"Inactive player '{first_name} {last_name}'")

        player_db.age = int(player[COL_AGE])
        player_db.salary_cap = float(player[COL_CAP_HIT]) * CAP_HIT_UNIT
        player_db.contract_expiration_season = season_id(int(player[COL_EXPIRATION_YEAR]))

        # `model_dump()` omits `_id`, which MongoDB rejects inside a $set.
        players_collection.update_one({'id': player_db.id}, {'$set': player_db.model_dump()}, upsert=True)

    logging.info(f"Not found players {len(not_found_players)}")
    logging.info(f"dupplicate name players {len(dupplicate_names_players)}")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    fetch_active_players()


if __name__ == "__main__":
    main()
