"""
The cumulator is where a first appearance used to produce wrong averages, so the
single-day cases below are the point of this file.
"""

import datetime

from nhl_helper.data.daily_leaders import (
    Decision,
    GoalieDailyStats,
    GoalieStats,
    MongoDailyLeaders,
    SkatersDailyStats,
    SkaterStats,
)
from nhl_helper.nhl.cumulate_active_players_stats import SeasonStats, accumulate_day, has_season_started
from nhl_helper.season import SeasonInfo


def skater(player_id: int, goals: int, assists: int) -> SkatersDailyStats:
    return SkatersDailyStats(
        id=player_id,
        name=f"skater-{player_id}",
        team=1,
        stats=SkaterStats(goals=goals, assists=assists, shootoutGoals=0),
    )


def goalie(player_id: int, shots: int, saves: int, decision: Decision | None) -> GoalieDailyStats:
    return GoalieDailyStats(
        id=player_id,
        name=f"goalie-{player_id}",
        team=1,
        stats=GoalieStats(
            goals=0, assists=0, shots=shots, saves=saves, savePercentage=0.0, starter=True, decision=decision
        ),
    )


def day(date: str, skaters=(), goalies=(), played=()) -> MongoDailyLeaders:
    return MongoDailyLeaders(date=date, skaters=list(skaters), goalies=list(goalies), played=list(played))


def cumulate(*days: MongoDailyLeaders) -> SeasonStats:
    stats = SeasonStats()
    games_played: dict[int, int] = {}
    for d in days:
        accumulate_day(stats, games_played, d)
    stats.finalize(games_played)
    return stats


def test_skater_seen_once_gets_a_real_points_per_game():
    stats = cumulate(day("2025-10-08", skaters=[skater(1, goals=2, assists=1)], played=[1]))

    result = stats.skaters[1]
    assert result.game_played == 1
    assert result.points == 3
    # Previously hardcoded to 0 on a player's first appearance.
    assert result.points_per_game == 3.0


def test_skater_totals_accumulate_across_days():
    stats = cumulate(
        day("2025-10-08", skaters=[skater(1, goals=2, assists=1)], played=[1]),
        day("2025-10-09", skaters=[skater(1, goals=0, assists=3)], played=[1]),
    )

    result = stats.skaters[1]
    assert (result.goals, result.assists, result.points) == (2, 4, 6)
    assert result.game_played == 2
    assert result.points_per_game == 3.0


def test_games_played_counts_scoreless_nights():
    stats = cumulate(
        day("2025-10-08", skaters=[skater(1, goals=2, assists=0)], played=[1]),
        day("2025-10-09", played=[1]),
    )

    result = stats.skaters[1]
    assert result.game_played == 2
    assert result.points == 2
    assert result.points_per_game == 1.0


def test_scorer_missing_from_played_does_not_raise():
    # A player with points but no recorded ice time used to raise KeyError.
    stats = cumulate(day("2025-10-08", skaters=[skater(1, goals=1, assists=0)], played=[]))

    result = stats.skaters[1]
    assert result.game_played == 0
    assert result.points_per_game == 0.0


def test_goalie_seen_once_gets_an_average_not_a_total():
    stats = cumulate(day("2025-10-08", goalies=[goalie(2, shots=30, saves=27, decision=Decision.W)], played=[2]))

    result = stats.goalies[2]
    assert result.game_played == 1
    assert result.wins == 1
    # 3 goals against over 1 game. This used to be stored as the raw goals against.
    assert result.goal_against_average == 3.0
    assert result.save_percentage == 0.9


def test_goalie_averages_over_multiple_games():
    stats = cumulate(
        day("2025-10-08", goalies=[goalie(2, shots=30, saves=27, decision=Decision.W)], played=[2]),
        day("2025-10-09", goalies=[goalie(2, shots=10, saves=9, decision=Decision.O)], played=[2]),
    )

    result = stats.goalies[2]
    assert result.game_played == 2
    assert (result.wins, result.ot) == (1, 1)
    assert (result.shots, result.saves) == (40, 36)
    assert result.goal_against_average == 2.0
    assert result.save_percentage == 0.9


def test_goalie_with_no_shots_does_not_divide_by_zero():
    stats = cumulate(day("2025-10-08", goalies=[goalie(2, shots=0, saves=0, decision=None)], played=[2]))

    result = stats.goalies[2]
    assert result.save_percentage == 0.0
    assert result.goal_against_average == 0.0


def test_documents_exclude_nothing_and_cover_both_groups():
    stats = cumulate(
        day(
            "2025-10-08",
            skaters=[skater(1, goals=1, assists=0)],
            goalies=[goalie(2, shots=10, saves=10, decision=Decision.W)],
            played=[1, 2],
        )
    )

    documents = stats.as_documents()
    assert set(documents) == {1, 2}
    assert documents[1]["points"] == 1
    assert documents[2]["wins"] == 1


def season_info(start: str) -> SeasonInfo:
    return SeasonInfo(
        start_season_date=start, end_season_date="2027-4-15", season=20262027, trade_deadline_date="2027-3-5"
    )


def test_offseason_does_not_cumulate():
    # The backend points at the next season months ahead; scanning that range
    # would erase every stat and recompute nothing.
    assert not has_season_started(datetime.date(2026, 9, 12), season_info("2026-9-29"))


def test_opening_day_morning_does_not_cumulate():
    assert not has_season_started(datetime.date(2026, 9, 29), season_info("2026-9-29"))


def test_day_after_opening_cumulates():
    assert has_season_started(datetime.date(2026, 9, 30), season_info("2026-9-29"))
