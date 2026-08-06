from datetime import date

from freezegun import freeze_time

from nhl_helper.utils.date import get_date_of_interest


@freeze_time("2026-03-12 03:00:00")
def test_before_noon_uses_yesterday():
    # Games finishing after midnight still belong to the previous day.
    assert get_date_of_interest() == date(2026, 3, 11)


@freeze_time("2026-03-12 11:59:00")
def test_just_before_noon_still_uses_yesterday():
    assert get_date_of_interest() == date(2026, 3, 11)


@freeze_time("2026-03-12 12:00:00")
def test_noon_switches_to_today():
    assert get_date_of_interest() == date(2026, 3, 12)


@freeze_time("2026-03-12 23:00:00")
def test_evening_uses_today():
    assert get_date_of_interest() == date(2026, 3, 12)
