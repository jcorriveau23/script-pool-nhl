# This scripts fetch live game data to list the best pointers of the day live.
# It store the information in the day_leaders collection in the mongoDB database.

from typing import Any
from pymongo import MongoClient
from datetime import date, datetime, timedelta
import requests
import json
import logging

from data.daily_leaders import DailyLeaders, GameType, GoalieDailyStats, GoalieStats, MongoDailyLeaders, SkaterStats, SkatersDailyStats
from utils.date import get_date_of_interest

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

def get_goalies_goals_and_assists(goalie_id: int, landing: Any)->tuple[int, int]:
    """
    Return the number of goalies goals and assists.
    These are not provided by the boxscore, but the game landing instead.
    """
    goals = 0
    assists = 0

    for period in landing["summary"]["scoring"]:
        for g in period["goals"]:
            if g["playerId"] == goalie_id:
                logging.info(f"{goalie_id} has a goal !")
                goals += 1

            for a in g["assists"]:
                if a["playerId"] == goalie_id:
                    logging.info(f"{goalie_id} has an assist!")
                    assists += 1

    return goals, assists

def fetch_pointers_day(date_of_interest: date | None = None):
    try:
        # To make sure that we fetch points of games that finish after 12AM, we fetch previous day before 12PM.
        if date_of_interest is None:
            date_of_interest = get_date_of_interest()

        day_leaders_data = get_day_leaders_data(date_of_interest)

        response = requests.request('GET', f"http://localhost:3000/api/games/{date_of_interest}")  # fetch all todays games
        today_games = json.loads(response.text)

        number_of_games = len(today_games["games"])
        logging.info(f'fetching for: {date_of_interest}, there is {number_of_games} games')

        for game in today_games["games"]:
            winning_goalie = None

            game_id = game['id']
            game_state = game['gameState']

            if game['gameType'] != GameType.REGULAR.value:
                logging.info(f"Skip the game! | Game Type: {game['gameType']}")
                continue

            if game_state != "LIVE" and game_state != "OFF" and game_state != "FINAL" and game_state != "CRIT":
                logging.info(f"Skip the game! | gameState: {game_state}")
                continue     # fetch the game stats until there is no more update

            if game_id in fetch_pointers_day.end_games:
                logging.info(f"Skip the game! | Game Ended: {game_id}")
                continue

            # Fetch the game boxscore and landing to be able to find every game information data.
            response = requests.request('GET', f'http://localhost:3000/api/game/{game_id}/boxscore')
            box_score = json.loads(response.text)

            response = requests.request('GET', f'http://localhost:3000/api/game/{game_id}/landing')
            landing = json.loads(response.text)

            shootout_scorer: dict[int, int] | None = None
            if box_score.get('gameOutcome') and box_score['gameOutcome']["lastPeriodType"] == "SO":
                shootout_scorer: dict[int, int] = {}

                for attempt in landing["summary"]["shootout"]:
                    if attempt["result"] == "goal":
                        print(f"{attempt["firstName"]} score in shootout")
                        # TODO: Get shootout pointers.
                        if attempt["playerId"] in shootout_scorer:
                            shootout_scorer[attempt["playerId"]] += 1
                        else:
                            shootout_scorer[attempt["playerId"]] = 1

            for side in ("awayTeam", "homeTeam"):
                for player in box_score['playerByGameStats'][side]["forwards"] + box_score['playerByGameStats'][side]["defense"]:
                    shootoutGoals = shootout_scorer.get(player['playerId'], 0) if shootout_scorer else 0
                    if player['goals'] > 0 or player['assists'] > 0 or shootoutGoals > 0: 
                        player_name = player['name']['default']
                        player_pts = player['goals'] + player['assists'] + shootoutGoals

                        logging.debug(f'{player_name} | {player_pts} pts')

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

                        logging.debug(f'{player_name} | goalies')

                        goals, assists = get_goalies_goals_and_assists(goalie['playerId'], landing)

                        update_goalies_stats(
                            day_leaders_data, GoalieDailyStats(
                                name=player_name,
                                id = goalie['playerId'],
                                team=box_score[side]['id'],
                                stats=GoalieStats(goals=goals, assists=assists, starter=goalie.get("starter", False), savePercentage=float(goalie.get("savePctg", "0.0")), decision=goalie.get("decision"))
                            )
                        )

                        if goalie['playerId'] not in day_leaders_data.played:
                            day_leaders_data.played.append(goalie['playerId'])

            if winning_goalie:              
                fetch_pointers_day.end_games.append(game_id)
                            
        day_leaders.update_one({'date': str(date_of_interest)}, {'$set': day_leaders_data.model_dump()}, upsert=True)
    except Exception as e:
        logging.error(str(e))


fetch_pointers_day.end_games = []

if __name__ == "__main__":
    start_date = date(2024, 10, 4)
    end_date = date.today()
    delta = timedelta(days=1)
    while start_date <= end_date:
       print(start_date)
       fetch_pointers_day(start_date)
       start_date += delta
    
    # fetch_pointers_day(date(2024, 10, 15))