# This scripts fetch live game data to list the best pointers of the day live.
# It store the information in the day_leaders collection in the mongoDB database.

from pymongo import MongoClient
from datetime import date, datetime, timedelta
import requests
import json

# create an client instance of the MongoDB class

mo_c = MongoClient()
db = mo_c.hockeypool

day_leaders = db.day_leaders
played = db.played

API_URL = 'https://api-web.nhle.com'

def get_day_leaders_data(day):
    day_leaders_data = day_leaders.find_one({"date": str(day)})
    if day_leaders_data is None:
        day_leaders_data = {
            'date': str(day),
            "skaters": [],
            "goalies": [],
            "played": []
            }

    return day_leaders_data

def get_played_data(day):
    played_data = played.find_one({"date": str(day)})
    if played_data is None:
        played_data = {
            'date': str(day),
            "players": []
            }
    return played_data

def update_skaters_stats(day_leaders_data, p):
    for player in day_leaders_data["skaters"]:
        if player["id"] == p["id"]:
            if player["stats"]["goals"] != p["stats"]["goals"] or player["stats"]["assists"] != p["stats"]["assists"] or player["stats"]["shootoutGoals"] != p["stats"]["shootoutGoals"]:
                date = day_leaders_data["date"]
                name = player["name"]
                past_goals = player["stats"]["goals"]
                new_goals = p["stats"]["goals"]
                past_assists = player["stats"]["assists"]
                new_assists = p["stats"]["assists"]
                print(f"Date: {date}, fix: {name}, G: {past_goals} -> {new_goals}, A: {past_assists} -> {new_assists}")
                player["stats"] = p["stats"]
            return
    
    day_leaders_data["skaters"].append(p)

def remove_skaters_stats(day_leaders_data, id):
    for player in day_leaders_data["skaters"]:
        if player["id"] == id:
            day_leaders_data["skaters"].remove(player)
            return

def update_goalies_stats(day_leaders_data, p):
    for player in day_leaders_data["goalies"]:
        if player["id"] == p["id"]:
            player["stats"] = p["stats"]
            return
    
    day_leaders_data["goalies"].append(p)

def _get_winning_goalie(day, game_id):
    TODAY_SCHEDULE_END_POINT = f'/v1/schedule/{day}'
    
    response = requests.request('GET', API_URL + TODAY_SCHEDULE_END_POINT)  # fetch all todays games
    schedule = json.loads(response.text)

    for week_day in schedule["gameWeek"]:
        if week_day["date"] == str(day):
            for game in week_day["games"]:
                if game["awayTeam"]["score"] > game["homeTeam"]["score"]:
                    winning_team = game["awayTeam"]["id"]
                else:
                    winning_team = game["homeTeam"]["id"]

                if game["id"] == game_id and "winningGoalie" in game:
                    return game["winningGoalie"], winning_team

def fetch_pointers_day(day: datetime.date | None = None):
    try:
        # To make sure that we fetch points of games that finish after 12AM, we fetch previous day before 12PM.
        if day is None:
            if datetime.now().hour < 12:
                day = date.today() - timedelta(days=1)
            else:
                day = date.today()

        day_leaders_data = get_day_leaders_data(day)
        played_data = get_played_data(day)
        TODAY_GAME_END_POINT = f'/v1/score/{day}'

        response = requests.request('GET', API_URL + TODAY_GAME_END_POINT)  # fetch all todays games
        today_games = json.loads(response.text)

        number_of_games = len(today_games["games"])
        print(f'fetching for: {day}, there is {number_of_games} games')
        for game in today_games["games"]:
            has_ot = False # tell if the game has been in shootout.
            winning_goalie = None

            game_id = game['id']
            game_state = game['gameState']

            if game['gameType'] != 2:
                print(f"Skip the game! | Game Type: {game['gameType']}")
                continue

            if game_state != "LIVE" and game_state != "OFF" and game_state != "FINAL":
                print(f"Skip the game! | gameState: {game_state}")
                continue     # fetch the game stats until there is no more update

            if game_id in fetch_pointers_day.end_games:
                print(f"Skip the game! | Game Ended: {game_id}")
                continue

            BOX_SCORE_END_POINT = f'/v1/gamecenter/{game_id}/boxscore'
            response = requests.request('GET', API_URL + BOX_SCORE_END_POINT)
            box_score = json.loads(response.text)

            GAME_END_POINT = f"/v1/gamecenter/{game_id}/landing"
            response = requests.request('GET', API_URL + GAME_END_POINT)
            game = json.loads(response.text)

            # When OT happens in the game we need to process the losing goalies points.
            if box_score['period'] > 3:
                has_ot = True

            # Try to get the winning goalie id.
            if game_state == "OFF" or game_state == "FINAL":
                winning_goalie, winning_team = _get_winning_goalie(day, game_id)

            for side in ("awayTeam", "homeTeam"):
                for player in box_score["boxscore"]['playerByGameStats'][side]["forwards"] + box_score["boxscore"]['playerByGameStats'][side]["defense"]:
                    if player['goals'] > 0 or player['assists'] > 0 or player['shPoints'] > 0: 
                        player_name = player['name']['default']
                        player_pts = player['goals'] + player['assists'] + player["shPoints"]

                        print(f'{player_name} | {player_pts} pts')

                        update_skaters_stats(day_leaders_data, {
                            'name': player_name, 
                            'id': player['playerId'],
                            'team': box_score[side]['id'],
                            'stats': {"goals": player["goals"], "assists": player["assists"], "shootoutGoals": player["shPoints"]}
                        })
                    else:
                        # Remove in case the player was given a points falsely.
                        remove_skaters_stats(day_leaders_data, player['playerId'])


                    if player.get('toi', "00:00") != '00:00':
                        if player['playerId'] not in played_data["players"]:
                            played_data["players"].append(player['playerId'])

                for goalie in box_score["boxscore"]['playerByGameStats'][side]["goalies"]:
                    if goalie.get('toi', "00:00") != '00:00':
                        player_name = goalie['name']['default']

                        print(f'{player_name} | goalies')

                        decision = None
                        if winning_goalie and winning_team:
                            if goalie['playerId'] == winning_goalie["playerId"]:
                                decision = "W"
                            elif box_score[side]['id'] != winning_team:
                                decision = "L"

                        update_goalies_stats(day_leaders_data, {
                            'name': player_name, 
                            'id': goalie['playerId'],
                            'team': box_score[side]['id'],
                            'stats': {
                                "goals": goalie.get("goals", 0), 
                                "assists": goalie.get("assists", 0), 
                                "OT": has_ot, 
                                "savePercentage": float(goalie.get("savePctg", "0.0")), 
                                "decision": decision 
                                }
                        })

                        if goalie['playerId'] not in played_data["players"]:
                            played_data["players"].append(goalie['playerId'])

            if winning_goalie:              
                fetch_pointers_day.end_games.append(game_id)
                            
        day_leaders_data["played"] = played_data["players"]
        day_leaders.update_one({'date': str(day)}, {'$set': day_leaders_data}, upsert=True)
        played.update_one({'date': str(day)}, {'$set': played_data}, upsert=True)

    except Exception as e:
        print("error")
        print(e)

fetch_pointers_day.end_games = []

if __name__ == "__main__":
    start_date = date(2023,11,7)
    end_date = date(2023,11,9)
    delta = timedelta(days=1)
    while start_date <= end_date:
       print(start_date)
       fetch_pointers_day(start_date)
       start_date += delta