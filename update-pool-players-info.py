from pymongo import MongoClient

from data.players_info import MongoPlayerInfo
mo_c = MongoClient()
db = mo_c.hockeypool

CURRENT_SEASON = 20242025

def update_pool_players(current_season: int)->None:
    """
    Parse all the player info of all pools and update their info.

    This require to have up to date players info in the `players` database. 
    """
    # A dictionnary savings up to date players info to avoid refetching them.
    player_id_to_player_info: dict[str, MongoPlayerInfo] = {}

    for pool in db.pools.find():
        # Only upate pool which are in the current season.
        if pool["season"] != current_season:
            continue

        for player_id in pool["context"]["players"].keys():
            player_id = str(player_id)

            if player_id_to_player_info.get(player_id) is None:
                results = db.players.find({"id": int(player_id)})
                players = [doc for doc in results]
                players[0].pop("game_played")
                players[0].pop("goals")
                players[0].pop("assists")
                players[0].pop("points")
                players[0].pop("points_per_game")
                players[0].pop("goal_against_average")
                players[0].pop("save_percentage")

                player_id_to_player_info[player_id] = players[0]
            
            pool["context"]["players"][player_id] = player_id_to_player_info[player_id]
                    

        db.pools.update_one({"name": pool["name"]}, {"$set": {f"context.players": pool["context"]["players"]}}, upsert=True)


if __name__ == "__main__":
    update_pool_players(CURRENT_SEASON)