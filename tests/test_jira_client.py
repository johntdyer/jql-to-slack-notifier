import pytest
from unittest.mock import MagicMock, patch
from src.jira_client import JiraClient

BASE_URL = "https://company.atlassian.net"


def _make_client():
    return JiraClient(base_url=BASE_URL, email="user@example.com", api_token="token123")


def _api_response(issues: list[dict]) -> MagicMock:
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {"issues": issues}
    return mock


def _raw_issue(key="PROJ-1", **fields):
    return {
        "key": key,
        "fields": {
            "summary": fields.get("summary", "Test summary"),
            "assignee": {"displayName": fields["assignee"]} if "assignee" in fields else None,
            "status": {"name": fields.get("status", "Open")},
            "priority": {"name": fields.get("priority", "Medium")},
            "issuetype": {"name": fields.get("issuetype", "Bug")},
            "reporter": {"displayName": fields["reporter"]} if "reporter" in fields else None,
        },
    }


class TestJiraClientSearch:
    def test_calls_correct_endpoint(self):
        client = _make_client()
        mock_resp = _api_response([])
        with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
            client.search("project = X", ["key", "summary"], max_results=10)
            url = mock_get.call_args[0][0]
            assert url == f"{BASE_URL}/rest/api/3/search/jql"

    def test_passes_jql_and_max_results(self):
        client = _make_client()
        mock_resp = _api_response([])
        with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
            client.search("project = X", ["key"], max_results=5)
            params = mock_get.call_args[1]["params"]
            assert params["jql"] == "project = X"
            assert params["maxResults"] == 5

    def test_raises_on_http_error(self):
        client = _make_client()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("404")
        with patch.object(client.session, "get", return_value=mock_resp):
            with pytest.raises(Exception, match="404"):
                client.search("project = X", ["key"])

    def test_returns_empty_list_when_no_issues(self):
        client = _make_client()
        with patch.object(client.session, "get", return_value=_api_response([])):
            result = client.search("project = X", ["key"])
            assert result == []

    def test_normalizes_key(self):
        client = _make_client()
        raw = [_raw_issue(key="PROJ-42")]
        with patch.object(client.session, "get", return_value=_api_response(raw)):
            result = client.search("project = X", ["key"])
            assert result[0]["key"] == "PROJ-42"

    def test_normalizes_summary(self):
        client = _make_client()
        raw = [_raw_issue(summary="My summary")]
        with patch.object(client.session, "get", return_value=_api_response(raw)):
            result = client.search("project = X", ["key", "summary"])
            assert result[0]["summary"] == "My summary"

    def test_normalizes_assignee_display_name(self):
        client = _make_client()
        raw = [_raw_issue(assignee="Jane Smith")]
        with patch.object(client.session, "get", return_value=_api_response(raw)):
            result = client.search("project = X", ["key", "assignee"])
            assert result[0]["assignee"] == "Jane Smith"

    def test_unassigned_issue(self):
        client = _make_client()
        raw = [_raw_issue()]  # no assignee key -> None
        with patch.object(client.session, "get", return_value=_api_response(raw)):
            result = client.search("project = X", ["key", "assignee"])
            assert result[0]["assignee"] == "Unassigned"

    def test_normalizes_status(self):
        client = _make_client()
        raw = [_raw_issue(status="In Progress")]
        with patch.object(client.session, "get", return_value=_api_response(raw)):
            result = client.search("project = X", ["key", "status"])
            assert result[0]["status"] == "In Progress"

    def test_normalizes_priority(self):
        client = _make_client()
        raw = [_raw_issue(priority="Critical")]
        with patch.object(client.session, "get", return_value=_api_response(raw)):
            result = client.search("project = X", ["key", "priority"])
            assert result[0]["priority"] == "Critical"

    def test_only_requested_fields_returned(self):
        client = _make_client()
        raw = [_raw_issue()]
        with patch.object(client.session, "get", return_value=_api_response(raw)):
            result = client.search("project = X", ["key", "summary"])
            assert "assignee" not in result[0]
            assert "status" not in result[0]

    def test_extra_api_fields_included_in_request(self):
        client = _make_client()
        with patch.object(client.session, "get", return_value=_api_response([])) as mock_get:
            client.search("project = X", ["key", "summary"], extra_api_fields=["parent"])
            params = mock_get.call_args[1]["params"]
            assert "parent" in params["fields"]

    def test_extra_api_fields_not_in_normalization(self):
        # extra_api_fields like "parent" must not appear in the normalized result as a plain key
        client = _make_client()
        raw = [_raw_issue()]
        with patch.object(client.session, "get", return_value=_api_response(raw)):
            result = client.search("project = X", ["key", "summary"], extra_api_fields=["parent"])
            # "parent" should not appear as a top-level key (it is extracted as parent_key)
            assert "parent" not in result[0]

    def test_normalizes_parent_key_for_subtask(self):
        client = _make_client()
        raw_issue = _raw_issue(key="CR-10")
        raw_issue["fields"]["parent"] = {"key": "STORY-5", "fields": {"summary": "Parent"}}
        with patch.object(client.session, "get", return_value=_api_response([raw_issue])):
            result = client.search("project = X", ["key", "summary"], extra_api_fields=["parent"])
            assert result[0]["parent_key"] == "STORY-5"

    def test_no_parent_key_when_no_parent_field(self):
        client = _make_client()
        raw = [_raw_issue()]  # no parent field in response
        with patch.object(client.session, "get", return_value=_api_response(raw)):
            result = client.search("project = X", ["key", "summary"])
            assert "parent_key" not in result[0]

    def test_issuetype_extracted_when_in_api_response_even_if_not_in_fields(self):
        # issuetype must be available to _enrich_parent_fields even when not a display field
        client = _make_client()
        raw = [_raw_issue(issuetype="Sub-task")]  # issuetype in raw response
        with patch.object(client.session, "get", return_value=_api_response(raw)):
            result = client.search("project = X", ["key", "summary"], extra_api_fields=["issuetype"])
            assert result[0]["issuetype"] == "Sub-task"


class TestJiraClientGetIssue:
    def test_calls_issue_endpoint(self):
        client = _make_client()
        raw = _raw_issue(key="STORY-1", summary="Parent story")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = raw
        with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
            client.get_issue("STORY-1", ["key", "summary"])
            url = mock_get.call_args[0][0]
            assert url == f"{BASE_URL}/rest/api/3/issue/STORY-1"

    def test_returns_normalized_fields(self):
        client = _make_client()
        raw = _raw_issue(key="STORY-1", summary="Parent story")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = raw
        with patch.object(client.session, "get", return_value=mock_resp):
            result = client.get_issue("STORY-1", ["key", "summary"])
            assert result["key"] == "STORY-1"
            assert result["summary"] == "Parent story"

    def test_resolves_custom_fields_via_field_map(self):
        client = _make_client()
        raw = _raw_issue(key="STORY-1")
        raw["fields"]["customfield_10102"] = "2025-06-30"
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = raw
        with patch.object(client.session, "get", return_value=mock_resp):
            result = client.get_issue(
                "STORY-1", ["Target end"], field_map={"Target end": "customfield_10102"}
            )
            assert result["Target end"] == "2025-06-30"

    def test_raises_on_http_error(self):
        client = _make_client()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("404")
        with patch.object(client.session, "get", return_value=mock_resp):
            with pytest.raises(Exception, match="404"):
                client.get_issue("MISSING-1", ["key"])
