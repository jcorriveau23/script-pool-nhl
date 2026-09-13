from datetime import date

import pytest

from nhl_helper.data.daily_leaders import (
    DailyLeaders,
    Decision,
    GoalieDailyStats,
    GoalieStats,
    SkatersDailyStats,
    SkaterStats,
)
from nhl_helper.nhl.get_daily_points_leaders import (
    get_goalies_goals_and_assists,
    is_in_season,
    remove_skaters_stats,
    update_goalies_stats,
    update_skaters_stats,
)
from nhl_helper.season import SeasonInfo


def empty_day() -> DailyLeaders:
    return DailyLeaders(date="2026-03-12", skaters=[], goalies=[], played=[])


def skater(player_id: int, goals: int, assists: int, shootout: int = 0) -> SkatersDailyStats:
    return SkatersDailyStats(
        id=player_id,
        name=f"skater-{player_id}",
        team=1,
        stats=SkaterStats(goals=goals, assists=assists, shootoutGoals=shootout),
    )


def goalie(player_id: int, saves: int, decision: Decision | None = None) -> GoalieDailyStats:
    return GoalieDailyStats(
        id=player_id,
        name=f"goalie-{player_id}",
        team=1,
        stats=GoalieStats(
            goals=0, assists=0, shots=30, saves=saves, savePercentage=0.9, starter=True, decision=decision
        ),
    )


def test_new_skater_is_appended():
    day = empty_day()
    update_skaters_stats(day, skater(1, goals=1, assists=0))

    assert [s.id for s in day.skaters] == [1]


def test_existing_skater_is_corrected_in_place():
    day = empty_day()
    update_skaters_stats(day, skater(1, goals=1, assists=0))
    update_skaters_stats(day, skater(1, goals=2, assists=1))

    assert len(day.skaters) == 1
    assert (day.skaters[0].stats.goals, day.skaters[0].stats.assists) == (2, 1)


def test_shootout_goal_correction_is_applied():
    day = empty_day()
    update_skaters_stats(day, skater(1, goals=1, assists=0, shootout=0))
    update_skaters_stats(day, skater(1, goals=1, assists=0, shootout=1))

    assert day.skaters[0].stats.shootoutGoals == 1


def test_remove_skater_drops_a_falsely_credited_player():
    day = empty_day()
    update_skaters_stats(day, skater(1, goals=1, assists=0))
    update_skaters_stats(day, skater(2, goals=1, assists=0))

    remove_skaters_stats(day, 1)

    assert [s.id for s in day.skaters] == [2]


def test_remove_skater_is_a_noop_when_absent():
    day = empty_day()
    update_skaters_stats(day, skater(1, goals=1, assists=0))

    remove_skaters_stats(day, 99)

    assert [s.id for s in day.skaters] == [1]


def test_goalie_decision_change_is_applied():
    day = empty_day()
    update_goalies_stats(day, goalie(3, saves=27, decision=None))
    update_goalies_stats(day, goalie(3, saves=28, decision=Decision.W))

    assert len(day.goalies) == 1
    assert day.goalies[0].stats.decision is Decision.W
    assert day.goalies[0].stats.saves == 28


def test_goalie_goals_and_assists_come_from_the_landing():
    landing = {
        "summary": {
            "scoring": [
                {
                    "goals": [
                        {"playerId": 100, "assists": [{"playerId": 55}, {"playerId": 42}]},
                        {"playerId": 55, "assists": []},
                    ]
                },
                {"goals": [{"playerId": 7, "assists": [{"playerId": 55}]}]},
            ]
        }
    }

    # The boxscore does not report goalie points, so they are read from the landing.
    assert get_goalies_goals_and_assists(55, landing) == (1, 2)
    assert get_goalies_goals_and_assists(999, landing) == (0, 0)


def season() -> SeasonInfo:
    return SeasonInfo(
        start_season_date=date(2026, 9, 29),
        end_season_date=date(2027, 4, 10),
        season=20262027,
        trade_deadline_date=date(2027, 3, 1),
    )


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        # Both bounds are in season: games are played on opening day, and a run
        # after midnight on the day after the last one still fetches it.
        (date(2026, 9, 29), True),
        (date(2027, 4, 10), True),
        (date(2027, 1, 15), True),
        # Offseason on either side of the backend's rollover.
        (date(2026, 9, 28), False),
        (date(2027, 4, 11), False),
        (date(2026, 7, 1), False),
    ],
)
def test_only_days_inside_the_season_window_are_polled(day, expected):
    assert is_in_season(day, season()) is expected
