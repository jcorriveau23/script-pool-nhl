import json

import pytest

from nhl_helper.nhl.get_active_contract_info import parse_players_array, season_id, split_player_name


@pytest.mark.parametrize(
    ("end_year", "expected"),
    [
        (26, 20252026),
        (30, 20292030),
        (0, 0),
        (-1, 0),
    ],
)
def test_season_id(end_year, expected):
    assert season_id(end_year) == expected


def test_season_id_pads_single_digit_years():
    # 2009-10 must be 20092010, not 209210.
    assert season_id(10) == 20092010


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("McDavid, Connor", ("Connor", "McDavid")),
        ("Connor McDavid", ("Connor", "McDavid")),
        ("  Connor McDavid  ", ("Connor", "McDavid")),
        # Multi-part surnames used to raise ValueError on unpacking.
        ("Pierre-Luc Dubois", ("Pierre-Luc", "Dubois")),
        ("Ryan Nugent Hopkins", ("Ryan", "Nugent Hopkins")),
    ],
)
def test_split_player_name(raw, expected):
    assert split_player_name(raw) == expected


def test_parse_players_array_reads_the_next_data_payload():
    payload = {"props": {"pageProps": {"playersArray": [["McDavid, Connor"], ["Matthews, Auston"]]}}}
    html = f'<html><body><script id="__NEXT_DATA__">{json.dumps(payload)}</script></body></html>'

    assert parse_players_array(html) == [["McDavid, Connor"], ["Matthews, Auston"]]


def test_parse_players_array_raises_when_the_layout_changes():
    with pytest.raises(RuntimeError, match="__NEXT_DATA__"):
        parse_players_array("<html><body><p>nothing here</p></body></html>")
