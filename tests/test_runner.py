import os
import pytest
from unittest.mock import MagicMock, patch, mock_open
from src.runner import load_config, run_named


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


class TestLoadConfig:
    def test_slack_none_in_yaml_does_not_raise(self, monkeypatch):
        """slack: with only a comment parses as None in PyYAML — must not TypeError."""
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
            run_named(config, "my query")  # lowercase — should not raise
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
