# this script will go through each pool in the database and cumulate the points of the players if it is not in the reservist. 

from pymongo import MongoClient
from datetime import date, timedelta

from data.constant import CURRENT_SEASON
import utils

# create an client instance of the MongoDB class

mo_c = MongoClient()
db = mo_c.hockeypool

def get_skaters_stats(id, today_pointers):
    for skater in today_pointers["skaters"]:
        if skater["id"] == id:
            if skater["stats"]["shootoutGoals"] > 0:
                return {
                    "G": skater["stats"]["goals"],
                    "A": skater["stats"]["assists"],
                    "SOG": skater["stats"]["shootoutGoals"]
                }
            else:
                return {
                    "G": skater["stats"]["goals"],
                    "A": skater["stats"]["assists"],
                }

    for skater in today_pointers["played"]:
        if skater == id:
            return {
                "G": 0,
                "A": 0
            }

def get_goalies_stats(id, today_pointers):
    for goalie in today_pointers["goalies"]:
        if goalie["id"] == id:
            return {
                "G": goalie["stats"]["goals"], 
                "A": goalie["stats"]["assists"], 
                "W": "decision" in goalie["stats"] and goalie["stats"]["decision"] == "W", 
                "SO": goalie["stats"]["starter"] == True and round(goalie["stats"]["savePercentage"], 3) == 1.000 and "decision" in goalie["stats"] and goalie["stats"]["decision"] == "W",
                "OT": "decision" in goalie["stats"] and goalie["stats"]["decision"] == "O", 
            }

def get_db_infos(day):
    return db.day_leaders.find_one({"date": str(day)})

def cumulate_daily_roster_pts(date_of_interest: date | None = None):
    """
    This function cumulate the daily roster points in the pool.
    This is being ran once a day to update pool database.
    """

    if date_of_interest is None:
        date_of_interest = utils.get_date_of_interest()

    today_pointers = get_db_infos(date_of_interest)

    if today_pointers is None:
       print(f"There is no data available for the {str(date_of_interest)}, no db update will be applied this itteration!")
       return

    if cumulate_daily_roster_pts.last_today_pointers == today_pointers:
       print("nothing as changed since the last update, no db update will be applied this itteration!")
       return

    cumulate_daily_roster_pts.last_today_pointers = today_pointers

    for pool in db.pools.find({"status": "InProgress"}):
        if pool["context"]["score_by_day"] is None:
            continue

        if pool["season"] != CURRENT_SEASON:
            continue

        score_by_day = pool["context"]["score_by_day"][str(date_of_interest)]

        for participant in pool["participants"]:
            participant_id = participant["id"]
            # Forward
            for key_forward in score_by_day[participant_id]["roster"]["F"]:
                player_stats = get_skaters_stats(int(key_forward), today_pointers)

                if score_by_day[participant_id]["roster"]["F"][key_forward] and player_stats != score_by_day[participant_id]["roster"]["F"][key_forward]:
                    name = pool["context"]["players"][key_forward]["name"]
                    past_goals = score_by_day[participant_id]["roster"]["F"][key_forward].get("G")
                    past_assists = score_by_day[participant_id]["roster"]["F"][key_forward].get("A")
                    new_goals = score_by_day[participant_id]["roster"]["F"][key_forward]["G"]
                    new_assists = score_by_day[participant_id]["roster"]["F"][key_forward]["A"]
                    print(f"Date: {str(date_of_interest)}, fix: {name}, G: {past_goals} -> {new_goals}, A: {past_assists} -> {new_assists}")
                score_by_day[participant_id]["roster"]["F"][key_forward] = player_stats



            # Defenders
            for key_defender in score_by_day[participant_id]["roster"]["D"]:
                player_stats = get_skaters_stats(int(key_defender), today_pointers)
                
                if score_by_day[participant_id]["roster"]["D"][key_defender] and player_stats != score_by_day[participant_id]["roster"]["D"][key_defender]:
                    name = pool["context"]["players"][key_defender]["name"]
                    past_goals = score_by_day[participant_id]["roster"]["D"][key_defender].get("G")
                    past_assists = score_by_day[participant_id]["roster"]["D"][key_defender].get("A")
                    new_goals = score_by_day[participant_id]["roster"]["D"][key_defender]["G"]
                    new_assists = score_by_day[participant_id]["roster"]["D"][key_defender]["A"]
                    print(f"Date: {str(date_of_interest)}, fix: {name}, G: {past_goals} -> {new_goals}, A: {past_assists} -> {new_assists}")

                score_by_day[participant_id]["roster"]["D"][key_defender] = player_stats
                    
            # Goalies
            for key_goaly in score_by_day[participant_id]["roster"]["G"]:
                score_by_day[participant_id]["roster"]["G"][key_goaly] = get_goalies_stats(int(key_goaly), today_pointers)
            
            # Set the is_cumulated value to True so that we know the points has been cumulated.
            score_by_day[participant_id]["is_cumulated"] = True

        db.pools.update_one({"name": pool["name"]}, {"$set": {f"context.score_by_day.{str(date_of_interest)}": score_by_day}}, upsert=True)

cumulate_daily_roster_pts.last_today_pointers = {}
cumulate_daily_roster_pts.last_played = {}

def lock_daily_roster(day = None):
    """
    Lock the daily roster of each pooler. 
    This is the roster that will be allow to cummulate points on that day.
    """
    if day is None:
        day = date.today()

    for pool in db.pools.find({"status": "InProgress"}):
        if pool["season"] != CURRENT_SEASON:
            continue
        
        daily_roster = {}
        for participant in pool["participants"]:
            participant_id = participant["id"]
            daily_roster[participant_id] = {}

            daily_roster[participant_id] = {"roster": {}, "is_cumulated": False}

            # Forwards

            daily_roster[participant_id]["roster"]["F"] = {}

            for forward_id in pool["context"]["pooler_roster"][participant_id]["chosen_forwards"]:
                daily_roster[participant_id]["roster"]["F"][str(forward_id)] = None

            # Defenders

            daily_roster[participant_id]["roster"]["D"] = {}

            for defender_id in pool["context"]["pooler_roster"][participant_id]["chosen_defenders"]:
                daily_roster[participant_id]["roster"]["D"][str(defender_id)] = None

            # Goalies

            daily_roster[participant_id]["roster"]["G"] = {}

            for goaly_id in pool["context"]["pooler_roster"][participant_id]["chosen_goalies"]:
                daily_roster[participant_id]["roster"]["G"][str(goaly_id)] = None

        if pool["context"]["score_by_day"] is None:
            # when score_by_day is null, at the begginning of the season, we need to initialize it.
            db.pools.update_one({"name": pool["name"]}, {"$set": {f"context.score_by_day": {}}}, upsert=True)

        db.pools.update_one({"name": pool["name"]}, {"$set": {f"context.score_by_day.{str(day)}": daily_roster}}, upsert=True)


if __name__ == "__main__":
    start_date = date(2024, 10, 4)
    end_date = date.today()
    delta = timedelta(days=1)
    while start_date <= end_date:
       print(start_date)
       # lock_daily_roster(start_date)
       cumulate_daily_roster_pts(start_date)
       start_date += delta

    # lock_daily_roster(date(2024, 12, 22))
    # cumulate_daily_roster_pts(date(2024, 12, 22))
