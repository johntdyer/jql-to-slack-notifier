import json
import logging
import requests

logger = logging.getLogger(__name__)


class SlackClient:
    API_URL = "https://slack.com/api/chat.postMessage"

    def __init__(self, bot_token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {bot_token}",
            "Content-Type": "application/json",
        })

    def post_message(self, channel: str, blocks: list[dict], text: str = "") -> dict:
        payload = {
            "channel": channel,
            "blocks": blocks,
            "text": text,  # fallback for notifications / accessibility
            "unfurl_links": True,
            "unfurl_media": False,
        }
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "curl -s -X POST %s \\\n"
                "  -H 'Authorization: Bearer ***' \\\n"
                "  -H 'Content-Type: application/json' \\\n"
                "  -d '%s'",
                self.API_URL,
                json.dumps(payload),
            )
        response = self.session.post(self.API_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API error: {data.get('error', 'unknown error')}")
        return data
