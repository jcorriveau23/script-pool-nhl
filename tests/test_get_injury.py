from nhl_helper.nhl.get_injury import parse_injured_players
from tests.test_find_players import FakeCollection, player_document


def injury_page(rows: list[tuple[str, str, str, str, str]]) -> str:
    """
    A minimal CBS injuries table: the player cell carries two links (the short
    and the full name) and parse_injured_players reads the second one.
    """
    body = "".join(
        f"<tr><td><a>short</a><a>{name}</a></td><td>{position}</td>"
        f"<td>{date}</td><td>{injury}</td><td>{recovery}</td></tr>"
        for name, position, date, injury, recovery in rows
    )
    return f"<table><tbody>{body}</tbody></table>"


def test_parsed_injury_carries_the_players_team():
    document = player_document("Brad Marchand", player_id=8473419)
    document["team"] = 13
    collection = FakeCollection([[document]])
    html = injury_page([("Brad Marchand", "LW", "Sat, Aug 15", "Lower Body", "Out until Oct 10")])

    injured = parse_injured_players(html, collection, [], {})

    assert injured[8473419].team == 13
    assert injured[8473419].model_dump() == {
        "name": "Brad Marchand",
        "position": "LW",
        "date": "Sat, Aug 15",
        "type": "Lower Body",
        "recovery": "Out until Oct 10",
        "team": 13,
    }


def test_player_without_a_team_is_written_with_a_null_team():
    document = player_document("Free Agent", player_id=1)
    document["team"] = None
    collection = FakeCollection([[document]])
    html = injury_page([("Free Agent", "C", "Mon, Sep 1", "Knee", "Out indefinitely")])

    injured = parse_injured_players(html, collection, [], {})

    assert injured[1].model_dump()["team"] is None


def test_unmatched_player_is_recorded_and_skipped():
    collection = FakeCollection([[], []])
    non_matching: dict[str, int | None] = {}
    html = injury_page([("Nobody Known", "D", "Mon, Sep 1", "Knee", "Out indefinitely")])

    injured = parse_injured_players(html, collection, [], non_matching)

    assert injured == {}
    assert non_matching == {"Nobody Known": None}
