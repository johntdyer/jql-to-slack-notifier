import os
import pytest
from unittest.mock import MagicMock, patch, mock_open
from src.runner import load_config, run_named, _merge_emoji_config, _enrich_parent_fields


MINIMAL_YAML = """
jira:
  base_url: https://company.atlassian.net
  email: user@example.com
slack: {}
queries:
  - name: My Query
    jql: "project = X"
    channel: "#eng"
    max_results: 10
    fields:
      - key
      - summary
      - status
"""

# Mirrors the real queries.yaml where slack: has only a comment (parsed as None by PyYAML)
NULL_SLACK_YAML = """
jira:
  base_url: https://company.atlassian.net
  email: user@example.com
slack:
queries:
  - name: My Query
    jql: "project = X"
    channel: "#eng"
    max_results: 10
    fields:
      - key
      - summary
      - status
"""


class TestMergeEmojiConfig:
    def test_both_none_returns_none(self):
        assert _merge_emoji_config(None, None) is None

    def test_empty_query_returns_global(self):
        global_cfg = {"header": ":bell:"}
        assert _merge_emoji_config(global_cfg, None) is global_cfg

    def test_empty_global_returns_query(self):
        query_cfg = {"header": ":fire:"}
        assert _merge_emoji_config(None, query_cfg) is query_cfg

    def test_empty_dict_query_treated_as_absent(self):
        global_cfg = {"header": ":bell:"}
        assert _merge_emoji_config(global_cfg, {}) is global_cfg

    def test_query_header_overrides_global(self):
        result = _merge_emoji_config({"header": ":bell:"}, {"header": ":rotating_light:"})
        assert result["header"] == ":rotating_light:"

    def test_global_header_preserved_when_absent_from_query(self):
        result = _merge_emoji_config({"header": ":bell:"}, {"status": {"open": ":white_circle:"}})
        assert result["header"] == ":bell:"

    def test_status_query_overrides_matching_global_entry(self):
        global_cfg = {"status": {"open": ":white_circle:", "done": ":white_check_mark:"}}
        query_cfg = {"status": {"open": ":large_green_circle:"}}
        result = _merge_emoji_config(global_cfg, query_cfg)
        assert result["status"]["open"] == ":large_green_circle:"
        assert result["status"]["done"] == ":white_check_mark:"

    def test_status_query_adds_new_entry(self):
        global_cfg = {"status": {"open": ":white_circle:"}}
        query_cfg = {"status": {"investigating": ":mag:"}}
        result = _merge_emoji_config(global_cfg, query_cfg)
        assert result["status"]["open"] == ":white_circle:"
        assert result["status"]["investigating"] == ":mag:"

    def test_priority_query_overrides_matching_global_entry(self):
        global_cfg = {"priority": {"high": ":red_circle:", "medium": ":large_yellow_circle:"}}
        query_cfg = {"priority": {"high": ":fire:"}}
        result = _merge_emoji_config(global_cfg, query_cfg)
        assert result["priority"]["high"] == ":fire:"
        assert result["priority"]["medium"] == ":large_yellow_circle:"

    def test_type_query_overrides_matching_global_entry(self):
        global_cfg = {"type": {"bug": ":bug:", "task": ":ballot_box_with_check:"}}
        query_cfg = {"type": {"bug": ":lady_beetle:"}}
        result = _merge_emoji_config(global_cfg, query_cfg)
        assert result["type"]["bug"] == ":lady_beetle:"
        assert result["type"]["task"] == ":ballot_box_with_check:"

    def test_global_missing_category_filled_from_query(self):
        global_cfg = {"header": ":bell:"}
        query_cfg = {"status": {"urgent": ":rotating_light:"}}
        result = _merge_emoji_config(global_cfg, query_cfg)
        assert result["status"] == {"urgent": ":rotating_light:"}

    def test_all_three_categories_merged_simultaneously(self):
        global_cfg = {
            "status": {"open": ":white_circle:"},
            "priority": {"high": ":red_circle:"},
            "type": {"bug": ":bug:"},
        }
        query_cfg = {
            "status": {"open": ":large_green_circle:"},
            "priority": {"high": ":fire:"},
            "type": {"bug": ":lady_beetle:"},
        }
        result = _merge_emoji_config(global_cfg, query_cfg)
        assert result["status"]["open"] == ":large_green_circle:"
        assert result["priority"]["high"] == ":fire:"
        assert result["type"]["bug"] == ":lady_beetle:"

    def test_does_not_mutate_global_config(self):
        global_cfg = {"header": ":bell:", "status": {"open": ":white_circle:"}}
        query_cfg = {"header": ":fire:", "status": {"open": ":red_circle:"}}
        _merge_emoji_config(global_cfg, query_cfg)
        assert global_cfg["header"] == ":bell:"
        assert global_cfg["status"]["open"] == ":white_circle:"


class TestLoadConfig:
    def test_slack_none_in_yaml_does_not_raise(self, monkeypatch):
        """slack: with only a comment parses as None in PyYAML -- must not TypeError."""
        monkeypatch.setenv("JIRA_API_TOKEN", "jira-secret")
        monkeypatch.setenv("SLACK_BOT_TOKEN", "slack-secret")
        with patch("builtins.open", mock_open(read_data=NULL_SLACK_YAML)):
            with patch("src.runner.load_dotenv"):
                config = load_config("config/queries.yaml")
        assert config["slack"]["bot_token"] == "slack-secret"

    def test_injects_jira_api_token_from_env(self, monkeypatch):
        monkeypatch.setenv("JIRA_API_TOKEN", "jira-secret")
        monkeypatch.setenv("SLACK_BOT_TOKEN", "slack-secret")
        with patch("builtins.open", mock_open(read_data=MINIMAL_YAML)):
            with patch("src.runner.load_dotenv"):
                config = load_config("config/queries.yaml")
        assert config["jira"]["api_token"] == "jira-secret"

    def test_injects_slack_bot_token_from_env(self, monkeypatch):
        monkeypatch.setenv("JIRA_API_TOKEN", "jira-secret")
        monkeypatch.setenv("SLACK_BOT_TOKEN", "slack-secret")
        with patch("builtins.open", mock_open(read_data=MINIMAL_YAML)):
            with patch("src.runner.load_dotenv"):
                config = load_config("config/queries.yaml")
        assert config["slack"]["bot_token"] == "slack-secret"

    def test_raises_when_jira_token_missing(self, monkeypatch):
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
        monkeypatch.setenv("SLACK_BOT_TOKEN", "slack-secret")
        with patch("builtins.open", mock_open(read_data=MINIMAL_YAML)):
            with patch("src.runner.load_dotenv"):
                with pytest.raises(KeyError):
                    load_config("config/queries.yaml")

    def test_raises_when_slack_token_missing(self, monkeypatch):
        monkeypatch.setenv("JIRA_API_TOKEN", "jira-secret")
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        with patch("builtins.open", mock_open(read_data=MINIMAL_YAML)):
            with patch("src.runner.load_dotenv"):
                with pytest.raises(KeyError):
                    load_config("config/queries.yaml")

    def test_parses_queries(self, monkeypatch):
        monkeypatch.setenv("JIRA_API_TOKEN", "x")
        monkeypatch.setenv("SLACK_BOT_TOKEN", "x")
        with patch("builtins.open", mock_open(read_data=MINIMAL_YAML)):
            with patch("src.runner.load_dotenv"):
                config = load_config("config/queries.yaml")
        assert len(config["queries"]) == 1
        assert config["queries"][0]["name"] == "My Query"


class TestRunNamed:
    def _config(self):
        return {
            "jira": {
                "base_url": "https://company.atlassian.net",
                "email": "u@example.com",
                "api_token": "x",
            },
            "slack": {"bot_token": "x"},
            "queries": [
                {
                    "name": "My Query",
                    "jql": "project = X",
                    "channel": "#eng",
                    "max_results": 10,
                    "fields": ["key", "summary", "status"],
                }
            ],
        }

    def test_raises_when_query_name_not_found(self):
        with pytest.raises(ValueError, match="not found"):
            run_named(self._config(), "Nonexistent Query")

    def test_error_message_lists_available_queries(self):
        with pytest.raises(ValueError, match="My Query"):
            run_named(self._config(), "Wrong Name")

    def test_matching_is_case_insensitive(self):
        config = self._config()
        with patch("src.runner._make_clients") as mock_clients:
            mock_jira = MagicMock()
            mock_slack = MagicMock()
            mock_jira.search.return_value = []
            mock_clients.return_value = (mock_jira, mock_slack)
            run_named(config, "my query")  # lowercase -- should not raise
            mock_jira.search.assert_called_once()

    def test_posts_to_correct_channel(self):
        config = self._config()
        with patch("src.runner._make_clients") as mock_clients:
            mock_jira = MagicMock()
            mock_slack = MagicMock()
            mock_jira.search.return_value = []
            mock_clients.return_value = (mock_jira, mock_slack)
            run_named(config, "My Query")
            call_kwargs = mock_slack.post_message.call_args[1]
            assert call_kwargs["channel"] == "#eng"


class TestEnrichParentFields:
    def _make_jira(self, parent_data: dict) -> MagicMock:
        jira = MagicMock()
        jira.get_issue.return_value = parent_data
        return jira

    def _subtask(self, key="CR-1", parent_key="STORY-10"):
        return {"key": key, "issuetype": "Sub-task", "parent_key": parent_key}

    def test_subtask_gets_parent_fields_fetched(self):
        issues = [self._subtask()]
        jira = self._make_jira({"key": "STORY-10", "Target end": "2025-06-30"})
        _enrich_parent_fields(issues, jira, ["Target end"], {"Target end": "customfield_10102"})
        jira.get_issue.assert_called_once_with("STORY-10", ["Target end"], {"Target end": "customfield_10102"})

    def test_parent_field_stored_with_arrow_prefix(self):
        issues = [self._subtask()]
        jira = self._make_jira({"key": "STORY-10", "Target end": "2025-06-30"})
        _enrich_parent_fields(issues, jira, ["Target end"], {})
        assert issues[0]["↑ Target end"] == "2025-06-30"

    def test_issue_without_parent_key_skipped(self):
        issues = [{"key": "CR-1", "issuetype": "Sub-task"}]  # no parent_key
        jira = self._make_jira({})
        _enrich_parent_fields(issues, jira, ["Target end"], {})
        jira.get_issue.assert_not_called()
        assert "↑ Target end" not in issues[0]

    def test_non_subtask_cr_types_are_skipped(self):
        for cr_type in ("Normal CR", "Emergency CR", "Standard CR", "Minor CR"):
            issues = [{"key": "CR-1", "issuetype": cr_type, "parent_key": "STORY-10"}]
            jira = self._make_jira({"key": "STORY-10", "Target end": "2025-06-30"})
            _enrich_parent_fields(issues, jira, ["Target end"], {})
            jira.get_issue.assert_not_called()
            assert "↑ Target end" not in issues[0]

    def test_subtask_type_case_insensitive(self):
        for st_type in ("Sub-task", "sub-task", "Subtask", "subtask"):
            issues = [{"key": "CR-1", "issuetype": st_type, "parent_key": "STORY-10"}]
            jira = self._make_jira({"key": "STORY-10", "Target end": "2025-06-30"})
            _enrich_parent_fields(issues, jira, ["Target end"], {})
            jira.get_issue.assert_called()

    def test_mixed_issue_types_only_subtasks_enriched(self):
        issues = [
            {"key": "CR-1", "issuetype": "Normal CR", "parent_key": "STORY-10"},
            {"key": "CR-2", "issuetype": "Sub-task", "parent_key": "STORY-10"},
        ]
        jira = self._make_jira({"key": "STORY-10", "Target end": "2025-06-30"})
        _enrich_parent_fields(issues, jira, ["Target end"], {})
        assert "↑ Target end" not in issues[0]
        assert issues[1]["↑ Target end"] == "2025-06-30"
        assert jira.get_issue.call_count == 1

    def test_parent_fetched_once_for_multiple_subtasks_same_parent(self):
        issues = [self._subtask("CR-1"), self._subtask("CR-2")]
        jira = self._make_jira({"key": "STORY-10", "Target end": "2025-06-30"})
        _enrich_parent_fields(issues, jira, ["Target end"], {})
        assert jira.get_issue.call_count == 1

    def test_different_parents_each_fetched_once(self):
        issues = [self._subtask("CR-1", "STORY-10"), self._subtask("CR-2", "STORY-20")]
        jira = MagicMock()
        jira.get_issue.side_effect = [
            {"key": "STORY-10", "Target end": "2025-06-01"},
            {"key": "STORY-20", "Target end": "2025-07-01"},
        ]
        _enrich_parent_fields(issues, jira, ["Target end"], {})
        assert jira.get_issue.call_count == 2
        assert issues[0]["↑ Target end"] == "2025-06-01"
        assert issues[1]["↑ Target end"] == "2025-07-01"

    def test_missing_parent_field_stored_as_empty_string(self):
        issues = [self._subtask()]
        jira = self._make_jira({"key": "STORY-10"})  # no "Target end" in parent data
        _enrich_parent_fields(issues, jira, ["Target end"], {})
        assert issues[0]["↑ Target end"] == ""
