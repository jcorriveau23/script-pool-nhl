



from dataclasses import asdict, dataclass
from pymongo import MongoClient
from constant import END_SEASON_DATE, START_SEASON_DATE
import datetime

from data.daily_leaders import Decision, MongoDailyLeaders

mo_c = MongoClient()
db = mo_c.hockeypool


@dataclass
class SkaterStats:
    game_played: int
    goals: int
    assists: int
    points: int
    points_per_game: int

    
@dataclass
class GoalieStats:
    game_played: int
    wins: int
    ot: int

def parse_all_season_players_stats() -> dict[str, SkaterStats | GoalieStats]:
    player_stats: dict[int, SkaterStats | GoalieStats] = {}

    start_date = START_SEASON_DATE
    end_date = END_SEASON_DATE
    delta = datetime.timedelta(days=1)
    number_of_games_per_player: dict[int, int] = {}

    while start_date <= end_date:

        # TODO: Get the daily leaders from database on that specific dates continue if there is no data for a specific date.
        doc = db.day_leaders.find_one({"date": str(start_date)})

        if doc is None:
            start_date += delta
            continue
        
        today_pointers: MongoDailyLeaders = MongoDailyLeaders(**doc)

        for p in today_pointers.played:
            if p not in number_of_games_per_player:
                number_of_games_per_player[p] = 0
            number_of_games_per_player[p] += 1
        
        for player in today_pointers.skaters:
            if player.id not in player_stats:
                player_stats[player.id] = SkaterStats(game_played=number_of_games_per_player[player.id], goals=player.stats.goals, assists=player.stats.assists, points=player.stats.goals + player.stats.assists, points_per_game=0)
            else:
                player_stats[player.id].game_played = number_of_games_per_player[player.id]
                player_stats[player.id].goals += player.stats.goals
                player_stats[player.id].assists += player.stats.assists
                player_stats[player.id].points += player.stats.goals + player.stats.assists
                player_stats[player.id].points_per_game = player_stats[player.id].points / player_stats[player.id].game_played
                

        for player in today_pointers.goalies:
            if player.id not in player_stats:
                player_stats[player.id] = GoalieStats(game_played=number_of_games_per_player[player.id], wins=1 if player.stats.decision == Decision.W else 0, ot=1 if player.stats.decision == Decision.O else 0)
            else:
                player_stats[player.id].game_played = number_of_games_per_player[player.id]
                player_stats[player.id].wins += 1 if player.stats.decision == Decision.W else 0
                player_stats[player.id].ot += 1 if player.stats.decision == Decision.O else 0

        start_date += delta
    
    return player_stats

def erase_player_stats()-> None:
    # Fields to set to null
    update_fields = {
        "assists": None,
        "game_played": None,
        "goal_against_average": None,
        "goals": None,
        "points": None,
        "points_per_game": None,
        "save_percentage": None
    }

    # Update all documents
    result = db.players.update_many({}, {"$set": update_fields})

def update_player_stats(player_stats: dict[int, SkaterStats | GoalieStats]) -> None:
    for player_id, stats in player_stats.items():
        # TODO: update the current player stats for the season.
        db.players.update_one({"id": player_id}, {"$set": asdict(stats)})

erase_player_stats()

player_stats = parse_all_season_players_stats()

update_player_stats(player_stats)