from personal_music_bot.sports import Sports


def test_extracts_standings_nested_under_season_groups() -> None:
    payload = {
        "children": [
            {
                "name": "2026",
                "standings": {
                    "entries": [{"team": {"id": "2688", "displayName": "Colo Colo"}, "rank": 1}]
                },
            }
        ]
    }

    rows = Sports._groups(payload)

    assert rows[0]["team"]["displayName"] == "Colo Colo"


def test_parses_goleadores_from_espn_stats_table() -> None:
    page = (
        '<tr data-idx="0"><td>1</td><td><a>Fernando Zampedri</a></td>'
        "<td>Universidad Católica</td><td>26</td><td>29</td></tr>"
    )

    assert Sports._scorer_rows(page) == [
        ["1", "Fernando Zampedri", "Universidad Católica", "26", "29"]
    ]


def test_reads_score_objects_returned_by_espn() -> None:
    assert Sports._score({"score": {"displayValue": "2", "value": 2}}) == "2"
    assert Sports._score({"score": "1"}) == "1"


def test_parses_player_stats_across_espn_categories() -> None:
    payload = {
        "splits": {
            "categories": [
                {"stats": [{"name": "appearances", "displayValue": "26"}]},
                {"stats": [{"name": "totalGoals", "value": 29}]},
            ]
        }
    }

    assert Sports._stat_values(payload) == {"appearances": "26", "totalGoals": "29"}


def test_formats_kickoff_in_chile_local_time() -> None:
    assert Sports._local_match_date("2026-12-01T23:30:00Z") == "01/12 · 20:30"
