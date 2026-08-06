from nhl_helper.utils.find_players import build_name_query, find_player_in_database_with_name


class FakeCollection:
    """
    Records the queries it is handed and replays canned results.
    """

    def __init__(self, results: list[list[dict]]):
        self._results = list(results)
        self.queries: list[dict] = []

    def find(self, query):
        self.queries.append(query)
        return iter(self._results.pop(0) if self._results else [])


def player_document(name: str, player_id: int = 1) -> dict:
    return {
        "id": player_id,
        "active": True,
        "name": name,
        "team": 1,
        "position": "F",
        "age": None,
        "salary_cap": None,
        "contract_expiration_season": None,
        "game_played": None,
        "goals": None,
        "assists": None,
        "points": None,
        "points_per_game": None,
        "goal_against_average": None,
        "save_percentage": None,
        "saves": None,
        "shots": None,
        "wins": None,
        "ot": None,
    }


def test_build_name_query_omits_active_when_not_requested():
    # `{"active": None}` matches nothing, so the key must be absent entirely.
    assert build_name_query("Connor McDavid", None) == {
        "name": {"$regex": "Connor McDavid", "$options": "i"}
    }


def test_build_name_query_includes_active_when_requested():
    assert build_name_query("Connor McDavid", False)["active"] is False


def test_regex_metacharacters_in_names_are_escaped():
    collection = FakeCollection([[player_document("T.J. Brodie")]])

    find_player_in_database_with_name(collection, "T.J.", "Brodie", True, [])

    # Unescaped, "T.J." would also match "TXJY", and a name containing "(" would
    # make MongoDB reject the pattern outright.
    assert collection.queries[0]["name"]["$regex"] == r"T\.J\.\ Brodie"


def test_fallback_query_keeps_the_active_filter_unset():
    collection = FakeCollection([[], [player_document("Connor McDavid")]])

    found = find_player_in_database_with_name(collection, "Conner", "McDavid", None, [])

    assert found is not None
    assert "active" not in collection.queries[1]
    assert collection.queries[1]["name"]["$regex"] == "McDavid$"


def test_duplicate_names_are_reported_and_skipped():
    duplicates: list[str] = []
    collection = FakeCollection([[player_document("Sebastian Aho", 1), player_document("Sebastian Aho", 2)]])

    assert find_player_in_database_with_name(collection, "Sebastian", "Aho", True, duplicates) is None
    assert duplicates == ["Sebastian Aho"]


def test_no_match_returns_none():
    collection = FakeCollection([[], []])

    assert find_player_in_database_with_name(collection, "Nobody", "Here", True, []) is None
