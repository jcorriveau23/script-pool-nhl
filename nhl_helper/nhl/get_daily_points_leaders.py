# This scripts fetch live game data to list the best pointers of the day live.
# It store the information in the day_leaders collection in the mongoDB database.

import argparse
import logging
from datetime import date, timedelta
from typing import Any

import requests

from nhl_helper.config import get_settings
from nhl_helper.data.daily_leaders import (
    DailyLeaders,
    GameType,
    GoalieDailyStats,
    GoalieStats,
    MongoDailyLeaders,
    SkatersDailyStats,
    SkaterStats,
)
from nhl_helper.db import get_database
from nhl_helper.utils.date import get_date_of_interest

# Games whose final stats have already been stored, so they no longer need polling.
_end_games: set[int] = set()


def get_day_leaders_data(day: date) -> MongoDailyLeaders:
    result = get_database().day_leaders.find_one({"date": str(day)})
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
            past_starter = old_player.stats.starter
            new_starter = new_player.stats.starter
            past_shots = old_player.stats.shots
            new_shots = new_player.stats.shots
            past_saves = old_player.stats.saves
            new_saves = new_player.stats.saves
            if past_goals != new_goals or past_assists != new_assists or past_decision != new_decision or past_starter != new_starter or past_shots != new_shots or past_saves != new_saves :
                logging.info(f"Date: {day_leaders_data.date}, fix: {new_player.name}, G: {past_goals} -> {new_goals}, A: {past_assists} -> {new_assists}, Decision: {past_decision} -> {new_decision}, Starter: {past_starter} -> {new_starter}")
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
    # To make sure that we fetch points of games that finish after 12AM, we fetch previous day before 12PM.
    if date_of_interest is None:
        date_of_interest = get_date_of_interest()

    settings = get_settings()
    timeout = settings.request_timeout_seconds

    day_leaders_data = get_day_leaders_data(date_of_interest)

    # fetch all todays games
    response = requests.get(f"{settings.nhl_proxy_url}/games/{date_of_interest}", timeout=timeout)
    response.raise_for_status()
    today_games = response.json()

    number_of_games = len(today_games["games"])
    logging.info(f'fetching for: {date_of_interest}, there is {number_of_games} games')

    for game in today_games["games"]:
        game_id = game['id']
        game_state = game['gameState']

        if game['gameType'] != GameType.REGULAR.value:
            logging.info(f"Skip the game! | Game Type: {game['gameType']}")
            continue

        if game_state != "LIVE" and game_state != "OFF" and game_state != "FINAL" and game_state != "CRIT":
            logging.info(f"Skip the game! | gameState: {game_state}")
            continue     # fetch the game stats until there is no more update

        if game_id in _end_games:
            logging.info(f"Skip the game! | Game Ended: {game_id}")
            continue

        # Fetch the game boxscore and landing to be able to find every game information data.
        response = requests.get(f'{settings.nhl_proxy_url}/game/{game_id}/boxscore', timeout=timeout)
        response.raise_for_status()
        box_score = response.json()

        response = requests.get(f'{settings.nhl_proxy_url}/game/{game_id}/landing', timeout=timeout)
        response.raise_for_status()
        landing = response.json()

        shootout_scorer: dict[int, int] = {}
        if box_score.get('gameOutcome') and box_score['gameOutcome']["lastPeriodType"] == "SO":
            for attempt in landing["summary"]["shootout"]["events"]:
                if isinstance(attempt, dict) and attempt.get("result") == "goal":
                    print(f"{attempt['firstName']} score in shootout")
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
                            stats=GoalieStats(goals=goals, 
                                              assists=assists, 
                                              starter=goalie.get("starter", False), 
                                              shots=goalie.get("shotsAgainst", 0),
                                              saves=goalie.get("saves", 0),
                                              savePercentage=float(goalie.get("savePctg", "0.0")), 
                                              decision=goalie.get("decision"))
                        )
                    )

                    if goalie['playerId'] not in day_leaders_data.played:
                        day_leaders_data.played.append(goalie['playerId'])

        # The game is over and its stats have just been stored, so there is
        # nothing left to poll for it today.
        if game_state in ("OFF", "FINAL"):
            _end_games.add(game_id)

    get_database().day_leaders.update_one(
        {'date': str(date_of_interest)}, {'$set': day_leaders_data.model_dump()}, upsert=True
    )


def main() -> None:
    """
    Fetch the day of interest by default, or backfill a date range with --start/--end.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, help="First day to fetch (YYYY-MM-DD).")
    parser.add_argument("--end", type=date.fromisoformat, help="Last day to fetch, inclusive. Defaults to --start.")
    args = parser.parse_args()

    if args.start is None:
        fetch_pointers_day()
        return

    current = args.start
    end = args.end or args.start
    while current <= end:
        logging.info(f"Backfilling {current}")
        fetch_pointers_day(current)
        current += timedelta(days=1)


if __name__ == "__main__":
    main()