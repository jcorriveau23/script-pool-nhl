from pymongo import MongoClient

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from data.players_info import MongoPlayerInfo
from data.constant import CURRENT_SEASON
mo_c = MongoClient()
db = mo_c.hockeypool

def get_all_pool_player_ids(pooler_roster: dict[str, any])->list[int]:
    """
    List of all pool player ids.
    """
    players: list[int] = []
    for roster in pooler_roster.values():
        players.extend(roster["chosen_forwards"] + roster["chosen_defenders"] + roster["chosen_goalies"] + roster["chosen_reservists"])

    return players




def update_pool_players(current_season: int)->None:
    """
    Parse all the player info of all pools and update their info.

    This require to have up to date players info in the `players` database. 
    """
    # A dictionnary savings up to date players info to avoid refetching them.
    player_id_to_player_info: dict[str, MongoPlayerInfo] = {}

    for pool in db.pools.find():
        # Only upate pool which are in the current season.
        if pool["season"] != current_season or pool["context"] is None:
            continue

        player_ids = get_all_pool_player_ids(pool["context"]["pooler_roster"])
        removed = 0

        print(pool["name"])
        print(player_ids)
        print(len(player_ids))


        for player_id in pool["context"]["players"].keys():
            player_id = str(player_id)

            if player_id_to_player_info.get(player_id) is None:
                results = db.players.find({"id": int(player_id)})
                players = [doc for doc in results]

                player_id_to_player_info[player_id] = players[0]
            
            if int(player_id) not in player_ids:
                removed += 1
                print(f"removed {removed}!")

            pool["context"]["players"][player_id] = player_id_to_player_info[player_id]
                    

        db.pools.update_one({"name": pool["name"]}, {"$set": {f"context.players": pool["context"]["players"]}}, upsert=True)


if __name__ == "__main__":
    update_pool_players(CURRENT_SEASON)