import logging
from typing import Any

from nhl_helper.db import get_database
from nhl_helper.season import get_season_info


def get_all_pool_player_ids(pooler_roster: dict[str, Any]) -> list[int]:
    """
    List of all pool player ids.
    """
    players: list[int] = []
    for roster in pooler_roster.values():
        players.extend(
            roster["chosen_forwards"] + roster["chosen_defenders"] + roster["chosen_goalies"] + roster["chosen_reservists"]
        )

    return players


def update_pool_players(current_season: int) -> None:
    """
    Parse all the player info of all pools and update their info.

    This require to have up to date players info in the `players` database.
    """
    db = get_database()

    # A dictionnary savings up to date players info to avoid refetching them.
    player_id_to_player_info: dict[str, Any] = {}

    for pool in db.pools.find():
        # Only upate pool which are in the current season.
        if pool["season"] != current_season or pool["context"] is None:
            continue

        player_ids = get_all_pool_player_ids(pool["context"]["pooler_roster"])
        removed = 0

        logging.info(f"{pool['name']}: {len(player_ids)} rostered players")

        for player_id in pool["context"]["players"]:
            player_id = str(player_id)

            if player_id_to_player_info.get(player_id) is None:
                player = db.players.find_one({"id": int(player_id)})

                if player is None:
                    logging.warning(f"Player {player_id} is not in the players collection; leaving pool entry as is.")
                    continue

                player_id_to_player_info[player_id] = player

            if int(player_id) not in player_ids:
                removed += 1

            pool["context"]["players"][player_id] = player_id_to_player_info[player_id]

        if removed:
            logging.info(f"{pool['name']}: {removed} players no longer on any roster")

        db.pools.update_one(
            {"name": pool["name"]}, {"$set": {"context.players": pool["context"]["players"]}}, upsert=True
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    update_pool_players(get_season_info().season)


if __name__ == "__main__":
    main()
