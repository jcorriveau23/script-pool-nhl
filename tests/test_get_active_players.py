import pytest

from nhl_helper.data.players_info import Position
from nhl_helper.nhl.get_active_players import _build_player_info, _get_position_code, _player_info_changed


@pytest.mark.parametrize(
    ("code", "expected"),
    [("R", Position.F), ("L", Position.F), ("C", Position.F), ("D", Position.D), ("G", Position.G), (None, None)],
)
def test_position_codes_map_to_pool_positions(code, expected):
    assert _get_position_code(code) is expected


def test_unknown_position_raises():
    with pytest.raises(ValueError, match="was not expected"):
        _get_position_code("X")


def nhl_player(active: bool = True, team_id: str | None = "22") -> dict:
    return {
        "playerId": "8478402",
        "name": "Connor McDavid",
        "positionCode": "C",
        "active": active,
        "teamId": team_id,
    }


def test_unchanged_player_is_not_flagged():
    # The search API returns teamId as a string; the database stores an int.
    assert _player_info_changed({"active": True, "team": 22}, nhl_player()) is False


def test_trade_is_flagged():
    assert _player_info_changed({"active": True, "team": 10}, nhl_player(team_id="22")) is True


def test_retirement_is_flagged():
    assert _player_info_changed({"active": True, "team": 22}, nhl_player(active=False)) is True


def test_player_without_a_team_is_handled():
    assert _player_info_changed({"active": True, "team": None}, nhl_player(team_id=None)) is False


def test_build_player_info_preserves_existing_stats():
    existing = {"age": 28, "goals": 5, "assists": 12, "points": 17, "salary_cap": 12500000.0}

    built = _build_player_info(nhl_player(), existing)

    assert built.id == 8478402
    assert built.team == 22
    assert built.position is Position.F
    # A roster refresh must not wipe accumulated stats.
    assert (built.goals, built.assists, built.points, built.age) == (5, 12, 17, 28)


def test_build_player_info_for_a_brand_new_player_leaves_stats_empty():
    built = _build_player_info(nhl_player(), None)

    assert built.goals is None
    assert built.salary_cap is None
    assert built.name == "Connor McDavid"
