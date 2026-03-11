from unittest.mock import MagicMock, patch

import pytest

from src.slash_handler import _list_response, _run_response, _RUN_QUERY_ACTION_ID, _query_subtitle


def _make_queries(*names):
    return [
        {
            "name": name,
            "jql": f"project = {name.upper().replace(' ', '_')}",
            "channel": "#test",
            "max_results": 10,
            "fields": ["key", "summary", "status"],
        }
        for name in names
    ]


def _section_rows(blocks):
    return [b for b in blocks if b["type"] == "section" and "accessory" in b]


# -- _query_subtitle ----------------------------------------------------------

class TestQuerySubtitle:
    def test_returns_description_when_present(self):
        assert _query_subtitle({"name": "Q", "description": "My description"}) == "My description"

    def test_returns_empty_when_no_description(self):
        assert _query_subtitle({"name": "Q", "channel": "#ch", "schedule": "0 9 * * 1-5"}) == ""


# -- _list_response -----------------------------------------------------------

class TestListResponse:
    def test_no_queries_returns_message(self):
        text, blocks = _list_response([])
        assert "No queries configured" in text
        assert blocks is None

    def test_returns_blocks_when_queries_exist(self):
        _, blocks = _list_response(_make_queries("Open Bugs"))
        assert blocks is not None

    def test_one_section_row_per_query(self):
        _, blocks = _list_response(_make_queries("Open Bugs", "Due This Week"))
        assert len(_section_rows(blocks)) == 2

    def test_section_text_contains_query_name(self):
        _, blocks = _list_response(_make_queries("Open Bugs"))
        row = _section_rows(blocks)[0]
        assert "Open Bugs" in row["text"]["text"]

    def test_section_text_starts_with_query_name(self):
        _, blocks = _list_response(_make_queries("Open Bugs"))
        row = _section_rows(blocks)[0]
        assert row["text"]["text"].startswith("*Open Bugs*")

    def test_description_shown_when_present(self):
        queries = [{"name": "My Query", "channel": "#ops", "description": "Shows open P0s",
                    "jql": "x", "max_results": 10, "fields": []}]
        _, blocks = _list_response(queries)
        text = _section_rows(blocks)[0]["text"]["text"]
        assert "Shows open P0s" in text

    def test_no_subtitle_when_description_absent(self):
        queries = [{"name": "My Query", "channel": "#ops", "schedule": "0 8 * * 1-5",
                    "jql": "x", "max_results": 10, "fields": []}]
        _, blocks = _list_response(queries)
        text = _section_rows(blocks)[0]["text"]["text"]
        assert "#ops" not in text
        assert "0 8 * * 1-5" not in text

    def test_accessory_is_button(self):
        _, blocks = _list_response(_make_queries("Open Bugs"))
        accessory = _section_rows(blocks)[0]["accessory"]
        assert accessory["type"] == "button"

    def test_button_label_is_run(self):
        _, blocks = _list_response(_make_queries("Open Bugs"))
        accessory = _section_rows(blocks)[0]["accessory"]
        assert accessory["text"]["text"] == "Run"

    def test_button_value_is_query_name(self):
        _, blocks = _list_response(_make_queries("Open Bugs"))
        accessory = _section_rows(blocks)[0]["accessory"]
        assert accessory["value"] == "Open Bugs"

    def test_button_action_id_uses_correct_prefix(self):
        _, blocks = _list_response(_make_queries("Q1", "Q2"))
        for row in _section_rows(blocks):
            assert row["accessory"]["action_id"].startswith(_RUN_QUERY_ACTION_ID + "__")

    def test_more_than_five_queries_all_rendered(self):
        queries = _make_queries("Q1", "Q2", "Q3", "Q4", "Q5", "Q6")
        _, blocks = _list_response(queries)
        assert len(_section_rows(blocks)) == 6


# -- _run_response ------------------------------------------------------------

class TestRunResponse:
    def _make_jira(self, issues=None):
        jira = MagicMock()
        jira.search.return_value = issues or []
        return jira

    def test_unknown_name_raises_value_error(self):
        queries = _make_queries("Real Query")
        with pytest.raises(ValueError, match="'Fake Query' not found"):
            _run_response("Fake Query", queries, self._make_jira(), "https://jira.example.com", None, "UTC")

    def test_error_lists_available_queries(self):
        queries = _make_queries("Query A", "Query B")
        with pytest.raises(ValueError, match="Query A") as exc:
            _run_response("Nope", queries, self._make_jira(), "https://jira.example.com", None, "UTC")
        assert "Query B" in str(exc.value)

    def test_match_is_case_insensitive(self):
        queries = _make_queries("Open Bugs")
        fallback, _ = _run_response(
            "open bugs", queries, self._make_jira(), "https://jira.example.com", None, "UTC"
        )
        assert "Open Bugs" in fallback

    def test_returns_fallback_text_with_count(self):
        queries = _make_queries("Open Bugs")
        issues = [{"key": "BUG-1", "summary": "A bug", "status": "Open"}]
        fallback, _ = _run_response(
            "Open Bugs", queries, self._make_jira(issues), "https://jira.example.com", None, "UTC"
        )
        assert "Open Bugs" in fallback
        assert "1" in fallback

    def test_returns_blocks_list(self):
        queries = _make_queries("Open Bugs")
        _, blocks = _run_response(
            "Open Bugs", queries, self._make_jira(), "https://jira.example.com", None, "UTC"
        )
        assert isinstance(blocks, list)
        assert len(blocks) > 0

    def test_passes_fields_to_jira_search(self):
        queries = [
            {
                "name": "My Query",
                "jql": "project = FOO",
                "channel": "#test",
                "max_results": 5,
                "fields": ["key", "summary", "priority"],
            }
        ]
        jira = self._make_jira()
        _run_response("My Query", queries, jira, "https://jira.example.com", None, "UTC")
        call_kwargs = jira.search.call_args
        assert call_kwargs.kwargs["fields"] == ["key", "summary", "priority"]
        assert call_kwargs.kwargs["max_results"] == 5

    def test_per_query_timezone_used(self):
        queries = [
            {
                "name": "TZ Query",
                "jql": "project = FOO",
                "channel": "#test",
                "max_results": 10,
                "fields": ["key", "summary"],
                "timezone": "America/New_York",
            }
        ]
        with patch("src.slash_handler.build_blocks") as mock_build:
            mock_build.return_value = [{"type": "section", "text": {"type": "mrkdwn", "text": "x"}}]
            _run_response("TZ Query", queries, self._make_jira(), "https://jira.example.com", None, "UTC")
            assert mock_build.call_args.kwargs["tz_name"] == "America/New_York"

    def test_emoji_config_merged_for_query(self):
        global_emojis = {"status": {"Open": ":white_circle:"}}
        queries = [
            {
                "name": "Emoji Query",
                "jql": "project = FOO",
                "channel": "#test",
                "max_results": 10,
                "fields": ["key", "summary"],
                "emojis": {"header": ":fire:"},
            }
        ]
        with patch("src.slash_handler.build_blocks") as mock_build:
            mock_build.return_value = [{"type": "section", "text": {"type": "mrkdwn", "text": "x"}}]
            _run_response("Emoji Query", queries, self._make_jira(), "https://jira.example.com", global_emojis, "UTC")
            effective = mock_build.call_args.kwargs["emoji_config"]
            assert effective["header"] == ":fire:"
            assert effective["status"] == {"Open": ":white_circle:"}
