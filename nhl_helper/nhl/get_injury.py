# This script fetch the current players injured in the nhl store it in a dictionnary and paste it in a static file inside the public folder.

import json
import logging

import requests
from bs4 import BeautifulSoup, Tag

from nhl_helper.config import get_settings
from nhl_helper.data.injured_players import InjuredPlayerInfo
from nhl_helper.db import get_database
from nhl_helper.utils.find_players import find_player_in_database_with_name


def parse_injured_players(
    html: str,
    players_collection,
    dupplicate_names_players: list[str],
    non_matching_players: dict[str, int | None],
) -> dict[int, InjuredPlayerInfo]:
    """
    Turn the CBS injuries page into a mapping of player id to injury info.

    Kept separate from the fetching and writing so it can be tested against a
    saved copy of the page.
    """
    injured_players: dict[int, InjuredPlayerInfo] = {}

    data = BeautifulSoup(html, 'lxml')
    for table in data.find_all("table"):
        body = table.tbody if isinstance(table, Tag) else None
        if body is None:
            continue

        for player in body.find_all("tr"):
            if not isinstance(player, Tag):
                continue

            tds = player.find_all("td")

            player_name: str = player.find_all("a")[1].text.strip()
            logging.info(f"{player_name} is currently injured.")
            first_name, last_name = player_name.split(" ", 1)

            player_found = find_player_in_database_with_name(
                players_collection, first_name, last_name, True, dupplicate_names_players
            )

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

    return injured_players


def fetch_injured_players_cbs() -> None:
    settings = get_settings()
    players_collection = get_database().players

    dupplicate_names_players: list[str] = []
    non_matching_players: dict[str, int | None] = {}

    response = requests.get(settings.cbs_injuries_url, timeout=settings.request_timeout_seconds)
    response.raise_for_status()

    injured_players = parse_injured_players(
        response.text, players_collection, dupplicate_names_players, non_matching_players
    )

    if not injured_players:
        # An empty result almost always means the CBS markup changed rather than
        # that the whole league is healthy, so refuse to overwrite the file.
        raise RuntimeError(
            f"No injured players parsed from {settings.cbs_injuries_url}; the page layout has probably changed."
        )

    serializable_data = {str(key): value.model_dump() for key, value in injured_players.items()}

    settings.injured_players_output.parent.mkdir(parents=True, exist_ok=True)
    with open(settings.injured_players_output, 'w') as json_file:
        json.dump(serializable_data, json_file, indent=4)

    with open(settings.non_matching_players_output, 'w') as json_file:
        json.dump(non_matching_players, json_file, indent=4)

    logging.info(
        f"{len(injured_players)} injured players written to {settings.injured_players_output}, "
        f"{len(non_matching_players)} unmatched."
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fetch_injured_players_cbs()


if __name__ == "__main__":
    main()
