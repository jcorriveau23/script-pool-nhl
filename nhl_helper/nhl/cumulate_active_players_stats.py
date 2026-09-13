"""
Rebuild every player's season totals in `db.players` from the daily leaders.

The job accumulates raw counting stats first and derives the averages once at
the end, so a player who only appears on a single day gets the same treatment as
one who appears every night.
"""

import datetime
import logging

from pydantic import BaseModel

from nhl_helper.data.daily_leaders import Decision, MongoDailyLeaders
from nhl_helper.db import get_database
from nhl_helper.season import SeasonInfo, get_season_info


class SkaterStats(BaseModel):
    active: bool = True
    game_played: int = 0
    goals: int = 0
    assists: int = 0
    points: int = 0
    points_per_game: float = 0.0


class GoalieStats(BaseModel):
    active: bool = True
    game_played: int = 0
    wins: int = 0
    ot: int = 0
    shots: int = 0
    saves: int = 0
    goal_against_average: float = 0.0
    save_percentage: float = 0.0


class SeasonStats(BaseModel):
    skaters: dict[int, SkaterStats] = {}
    goalies: dict[int, GoalieStats] = {}

    def finalize(self, games_played: dict[int, int]) -> None:
        """
        Apply games played and derive every average, for first-timers included.
        """
        for player_id, skater in self.skaters.items():
            skater.game_played = games_played.get(player_id, 0)
            skater.points_per_game = round(skater.points / skater.game_played, 4) if skater.game_played else 0.0

        for player_id, goalie in self.goalies.items():
            goalie.game_played = games_played.get(player_id, 0)
            goalie.save_percentage = round(goalie.saves / goalie.shots, 4) if goalie.shots else 0.0
            goals_against = goalie.shots - goalie.saves
            goalie.goal_against_average = (
                round(goals_against / goalie.game_played, 4) if goalie.game_played else 0.0
            )

    def as_documents(self) -> dict[int, dict]:
        return {player_id: stats.model_dump() for player_id, stats in (self.skaters | self.goalies).items()}


def accumulate_day(stats: SeasonStats, games_played: dict[int, int], day: MongoDailyLeaders) -> None:
    """
    Fold a single day of leaders into the running totals.
    """
    for player_id in day.played:
        games_played[player_id] = games_played.get(player_id, 0) + 1

    for player in day.skaters:
        skater = stats.skaters.setdefault(player.id, SkaterStats())
        skater.goals += player.stats.goals
        skater.assists += player.stats.assists
        skater.points += player.stats.goals + player.stats.assists

    for goalie_of_day in day.goalies:
        goalie = stats.goalies.setdefault(goalie_of_day.id, GoalieStats())
        goalie.wins += 1 if goalie_of_day.stats.decision == Decision.W else 0
        goalie.ot += 1 if goalie_of_day.stats.decision == Decision.O else 0
        goalie.shots += goalie_of_day.stats.shots
        goalie.saves += goalie_of_day.stats.saves


def parse_all_season_players_stats() -> SeasonStats:
    season = get_season_info()
    db = get_database()

    stats = SeasonStats()
    games_played: dict[int, int] = {}

    current = season.start_season_date
    delta = datetime.timedelta(days=1)

    while current <= season.end_season_date:
        doc = db.day_leaders.find_one({"date": str(current)})

        if doc is not None:
            accumulate_day(stats, games_played, MongoDailyLeaders(**doc))

        current += delta

    stats.finalize(games_played)
    return stats


def erase_player_stats() -> None:
    # Fields to set to null
    update_fields = {
        "assists": None,
        "game_played": None,
        "goal_against_average": None,
        "goals": None,
        "points": None,
        "points_per_game": None,
        "save_percentage": None,
        "wins": None,
        "ot": None,
        "saves": None,
        "shots": None,
    }

    # Update all documents
    get_database().players.update_many({}, {"$set": update_fields})


def update_player_stats(stats: SeasonStats) -> None:
    players = get_database().players
    for player_id, document in stats.as_documents().items():
        players.update_one({"id": player_id}, {"$set": document})


def has_season_started(today: datetime.date, season: SeasonInfo) -> bool:
    """
    Whether there is at least one completed day of the season to cumulate.

    The backend rolls `GET /season-info` over to the next season months before
    it starts, so most of the year the range this job would scan holds no
    `day_leaders` at all. Running anyway erases every player's stats and then
    recomputes nothing, which is why this is checked before anything is written.

    The start date itself does not count: no game has finished when the job runs
    on the morning of opening day.
    """
    return today > season.start_season_date


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    season = get_season_info()

    if not has_season_started(datetime.date.today(), season):
        logging.info(
            f"Season {season.season} starts {season.start_season_date} and has no completed days yet; "
            "leaving the current stats alone."
        )
        return

    # Cumulate before erasing, not after: the stats are null between the two
    # calls, and any job that reads a player in that window writes the nulls
    # back. Season-long scan first keeps that window to the writes themselves.
    stats = parse_all_season_players_stats()
    logging.info(f"{len(stats.skaters)} skaters and {len(stats.goalies)} goalies cumulated")

    if not stats.skaters and not stats.goalies:
        # In season with nothing to show means the daily job stopped filling
        # `day_leaders`, not that nobody has scored. Erasing here would throw
        # away the only remaining copy of the totals.
        raise RuntimeError(
            f"No day_leaders found between {season.start_season_date} and {season.end_season_date}; "
            "refusing to erase the stats already on record."
        )

    erase_player_stats()
    update_player_stats(stats)


if __name__ == "__main__":
    main()
