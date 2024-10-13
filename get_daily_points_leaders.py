# This scripts fetch live game data to list the best pointers of the day live.
# It store the information in the day_leaders collection in the mongoDB database.

from pymongo import MongoClient
from datetime import date, datetime, timedelta
import requests
import json
import logging

from data.daily_leaders import DailyLeaders, GameType, GoalieDailyStats, GoalieStats, MongoDailyLeaders, SkaterStats, SkatersDailyStats

# create an client instance of the MongoDB class

mo_c = MongoClient()
db = mo_c.hockeypool

day_leaders = db.day_leaders
played = db.played

API_URL = 'https://api-web.nhle.com'

def get_day_leaders_data(day: date) -> MongoDailyLeaders:
    result = day_leaders.find_one({"date": str(day)})
    if result is None:
        return MongoDailyLeaders(
            date = str(day),
            skaters = [],
            goalies = [],
            played = []
        )
    
    return MongoDailyLeaders(**result)

def update_skaters_stats(day_leaders_data: DailyLeaders, new_player: SkatersDailyStats):
    for old_player in day_leaders_data.skaters:
        if old_player.id == new_player.id:
            past_goals = old_player.stats.goals
            new_goals = new_player.stats.goals
            past_assists = old_player.stats.assists
            new_assists = new_player.stats.assists
            past_shootout_goals = old_player.stats.shootoutGoals
            new_shootout_goals = new_player.stats.shootoutGoals
            if past_goals != new_goals or past_assists != new_assists or past_shootout_goals != new_shootout_goals:
                logging.info(f"Date: {day_leaders_data.date}, fix: {new_player.name}, G: {past_goals} -> {new_goals}, A: {past_assists} -> {new_assists}, SOG {past_shootout_goals} -> {new_shootout_goals}")
                old_player.stats = new_player.stats
            return
    
    day_leaders_data.skaters.append(new_player)

def remove_skaters_stats(day_leaders_data: DailyLeaders, id: int):
    for player in day_leaders_data.skaters:
        if player.id == id:
            day_leaders_data.skaters.remove(player)
            return

def update_goalies_stats(day_leaders_data: DailyLeaders, new_player: GoalieDailyStats):
    for old_player in day_leaders_data.goalies:
        if old_player.id == new_player.id:
            past_goals = old_player.stats.goals
            new_goals = new_player.stats.goals
            past_assists = old_player.stats.assists
            new_assists = new_player.stats.assists
            past_decision = old_player.stats.decision
            new_decision = new_player.stats.decision
            if past_goals != new_goals or past_assists != new_assists or past_decision != new_decision:
                logging.info(f"Date: {day_leaders_data.date}, fix: {new_player.name}, G: {past_goals} -> {new_goals}, A: {past_assists} -> {new_assists}, Decision: {past_decision} -> {new_decision}")
                old_player.stats = new_player.stats
            return
    
    day_leaders_data.goalies.append(new_player)

def fetch_pointers_day(day: date | None = None):
    try:
        # To make sure that we fetch points of games that finish after 12AM, we fetch previous day before 12PM.
        if day is None:
            if datetime.now().hour < 12:
                day = date.today() - timedelta(days=1)
            else:
                day = date.today()

        day_leaders_data = get_day_leaders_data(day)

        response = requests.request('GET', f"http://localhost:3000/api/games/{day}")  # fetch all todays games
        today_games = json.loads(response.text)

        number_of_games = len(today_games["games"])
        print(f'fetching for: {day}, there is {number_of_games} games')

        for game in today_games["games"]:
            winning_goalie = None

            game_id = game['id']
            game_state = game['gameState']

            if game['gameType'] != GameType.REGULAR.value:
                print(f"Skip the game! | Game Type: {game['gameType']}")
                continue

            if game_state != "LIVE" and game_state != "OFF" and game_state != "FINAL" and game_state != "CRIT":
                print(f"Skip the game! | gameState: {game_state}")
                continue     # fetch the game stats until there is no more update

            if game_id in fetch_pointers_day.end_games:
                print(f"Skip the game! | Game Ended: {game_id}")
                continue

            BOX_SCORE_END_POINT = f'/v1/gamecenter/{game_id}/boxscore'
            response = requests.request('GET', API_URL + BOX_SCORE_END_POINT)
            box_score = json.loads(response.text)

            shootout_scorer: dict[int, int] | None = None
            if box_score.get('gameOutcome') == "SO":
                # TODO: Get shootout pointers.
                shootout_scorer: dict[int, int] = {}
                pass

            for side in ("awayTeam", "homeTeam"):
                for player in box_score['playerByGameStats'][side]["forwards"] + box_score['playerByGameStats'][side]["defense"]:
                    shootoutGoals = shootout_scorer.get(player['playerId'], 0) if shootout_scorer else 0
                    if player['goals'] > 0 or player['assists'] > 0 or shootoutGoals > 0: 
                        player_name = player['name']['default']
                        player_pts = player['goals'] + player['assists'] + shootoutGoals

                        print(f'{player_name} | {player_pts} pts')

                        update_skaters_stats(
                            day_leaders_data, 
                            SkatersDailyStats(
                                name=player_name,
                                id = player['playerId'],
                                team=box_score[side]['id'],
                                stats=SkaterStats(goals=player["goals"], assists=player["assists"], shootoutGoals=shootoutGoals)
                            )
                        )
                    else:
                        # Remove in case the player was given a points falsely.
                        remove_skaters_stats(day_leaders_data, player['playerId'])

                    if player.get('toi', "00:00") != '00:00':
                        if player['playerId'] not in day_leaders_data.played:
                            day_leaders_data.played.append(player['playerId'])

                for goalie in box_score['playerByGameStats'][side]["goalies"]:
                    if goalie.get('toi', "00:00") != '00:00':
                        player_name = goalie['name']['default']

                        print(f'{player_name} | goalies')

                        update_goalies_stats(
                            day_leaders_data, GoalieDailyStats(
                                name=player_name,
                                id = goalie['playerId'],
                                team=box_score[side]['id'],
                                stats=GoalieStats(goals=goalie.get("goals", 0), assists=goalie.get("assists", 0), savePercentage=float(goalie.get("savePctg", "0.0")), decision=goalie.get("decision"))
                            )
                        )

                        if goalie['playerId'] not in day_leaders_data.played:
                            day_leaders_data.played.append(goalie['playerId'])

            if winning_goalie:              
                fetch_pointers_day.end_games.append(game_id)
                            
        day_leaders.update_one({'date': str(day)}, {'$set': day_leaders_data.model_dump()}, upsert=True)
    except Exception as e:
        logging.error(str(e))


fetch_pointers_day.end_games = []

if __name__ == "__main__":
    # start_date = date(2023,11,7)
    # end_date = date(2023,11,9)
    # delta = timedelta(days=1)
    # while start_date <= end_date:
    #    print(start_date)
    #    fetch_pointers_day(start_date)
    #    start_date += delta
    
    fetch_pointers_day(date(2024, 10, 12))