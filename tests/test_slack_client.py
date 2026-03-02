import pytest
from unittest.mock import MagicMock, patch
from src.slack_client import SlackClient


def _make_client():
    return SlackClient(bot_token="xoxb-test-token")


def _mock_response(ok: bool, error: str = "") -> MagicMock:
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    payload = {"ok": ok}
    if error:
        payload["error"] = error
    mock.json.return_value = payload
    return mock


class TestSlackClientPostMessage:
    def test_posts_to_correct_url(self):
        client = _make_client()
        with patch.object(client.session, "post", return_value=_mock_response(True)) as mock_post:
            client.post_message("#general", blocks=[], text="hi")
            url = mock_post.call_args[0][0]
            assert url == "https://slack.com/api/chat.postMessage"

    def test_sends_channel_and_blocks(self):
        client = _make_client()
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "hello"}}]
        with patch.object(client.session, "post", return_value=_mock_response(True)) as mock_post:
            client.post_message("#eng", blocks=blocks, text="fallback")
            payload = mock_post.call_args[1]["json"]
            assert payload["channel"] == "#eng"
            assert payload["blocks"] == blocks
            assert payload["text"] == "fallback"
            assert payload["unfurl_links"] is True
            assert payload["unfurl_media"] is False

    def test_raises_on_http_error(self):
        client = _make_client()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("500")
        with patch.object(client.session, "post", return_value=mock_resp):
            with pytest.raises(Exception, match="500"):
                client.post_message("#general", blocks=[])

    def test_raises_on_slack_api_error(self):
        client = _make_client()
        with patch.object(client.session, "post", return_value=_mock_response(False, "channel_not_found")):
            with pytest.raises(RuntimeError, match="channel_not_found"):
                client.post_message("#missing", blocks=[])

    def test_returns_response_data_on_success(self):
        client = _make_client()
        with patch.object(client.session, "post", return_value=_mock_response(True)):
            result = client.post_message("#general", blocks=[])
            assert result["ok"] is True

    def test_authorization_header_set(self):
        client = _make_client()
        assert client.session.headers["Authorization"] == "Bearer xoxb-test-token"
