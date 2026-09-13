import logging

import requests

from nhl_helper.config import get_settings
from nhl_helper.data import players_info
from nhl_helper.db import get_database

LIMIT = 300000
ACTIVE = True


def _get_position_code(position: str | None) -> players_info.Position | None:
    match position:
        case "R" | "L" | "C":
            return players_info.Position.F
        case "D":
            return players_info.Position.D
        case "G":
            return players_info.Position.G
        case None:
            return None
        case _:
            raise ValueError(f"The position {position} was not expected.")


def _player_info_changed(database_player: dict, nhl_player: dict) -> bool:
    database_team_id = database_player.get("team")
    new_team_id = nhl_player.get("teamId")
    # The search API returns teamId as a string, the database stores it as an int.
    return database_player["active"] != nhl_player["active"] or (
        str(database_team_id) if database_team_id is not None else None
    ) != new_team_id


def _build_player_info(nhl_player: dict, existing: dict | None) -> players_info.PlayerInfo:
    """
    Build the document to store, carrying over any stats already on record.
    """
    existing = existing or {}
    team_id = nhl_player.get("teamId")

    return players_info.PlayerInfo(
        id=int(nhl_player["playerId"]),
        active=nhl_player["active"],
        name=nhl_player["name"],
        team=int(team_id) if team_id is not None else None,
        position=_get_position_code(nhl_player["positionCode"]),
        age=existing.get("age"),
        salary_cap=existing.get("salary_cap"),
        contract_expiration_season=existing.get("contract_expiration_season"),
        game_played=existing.get("game_played"),
        goals=existing.get("goals"),
        assists=existing.get("assists"),
        points=existing.get("points"),
        points_per_game=existing.get("points_per_game"),
        goal_against_average=existing.get("goal_against_average"),
        save_percentage=existing.get("save_percentage"),
        wins=existing.get("wins"),
        ot=existing.get("ot"),
        saves=existing.get("saves"),
        shots=existing.get("shots"),
    )


def get_active_players() -> None:
    settings = get_settings()
    url = f"{settings.nhl_search_url}?culture=en-us&limit={LIMIT}&q=*&active={ACTIVE}"

    response = requests.get(url, timeout=settings.request_timeout_seconds)
    response.raise_for_status()
    active_players = response.json()

    players_collection = get_database().players

    logging.info(f"{len(active_players)} players found.")

    players_not_updated = 0
    players_updated_in_database = 0

    for nhl_player in active_players:
        player_id = int(nhl_player["playerId"])
        existing = players_collection.find_one({'id': player_id})

        if existing is None:
            stored_player_info = _build_player_info(nhl_player, None)
            logging.info(f"Added {stored_player_info.name} to the database.")
        elif _player_info_changed(existing, nhl_player):
            stored_player_info = _build_player_info(nhl_player, existing)
            logging.info(f"{nhl_player['name']} info updated.")
        else:
            players_not_updated += 1
            continue

        players_updated_in_database += 1
        players_collection.update_one({'id': player_id}, {'$set': stored_player_info.model_dump()}, upsert=True)

    logging.info(f"{players_updated_in_database} updated and {players_not_updated} already in database.")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    get_active_players()


if __name__ == "__main__":
    main()
