"""
The season payload is hand-maintained in the backend, so the parsing here has to
tolerate the shapes it actually returns rather than the one it should.
"""

from datetime import date

import pytest

from nhl_helper.season import SeasonInfo, parse_season_date


def test_parses_the_documented_payload():
    info = SeasonInfo(
        **{
            "start_season_date": "2026-09-29",
            "end_season_date": "2027-04-10",
            "season": 20262027,
            "trade_deadline_date": "2027-03-01",
        }
    )

    assert info.start_season_date == date(2026, 9, 29)
    assert info.end_season_date == date(2027, 4, 10)
    assert info.season == 20262027
    assert info.trade_deadline_date == date(2027, 3, 1)


@pytest.mark.parametrize("value", ["2025-10-7", "2025-10-07"])
def test_accepts_unpadded_days(value):
    # The backend has shipped both forms; date.fromisoformat rejects the first.
    assert parse_season_date(value) == date(2025, 10, 7)


def test_unpadded_dates_survive_the_model():
    info = SeasonInfo(
        **{
            "start_season_date": "2025-10-7",
            "end_season_date": "2026-4-16",
            "season": 20252026,
            "trade_deadline_date": "2026-3-7",
        }
    )

    assert info.start_season_date == date(2025, 10, 7)
    assert info.end_season_date == date(2026, 4, 16)
    assert info.trade_deadline_date == date(2026, 3, 7)
