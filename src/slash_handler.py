import os
import re

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from .formatter import build_blocks
from .runner import _enrich_parent_fields, _make_clients, _merge_emoji_config

_RUN_QUERY_ACTION_ID = "run_query"


def _query_subtitle(q: dict) -> str:
    return q.get("description", "")


def _list_response(queries: list[dict]) -> tuple[str, list[dict] | None]:
    if not queries:
        return "No queries configured.", None

    rows = []
    for i, q in enumerate(queries):
        subtitle = _query_subtitle(q)
        text = f"*{q['name']}*" + (f"\n{subtitle}" if subtitle else "")
        rows.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": text},
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Run"},
                "action_id": f"{_RUN_QUERY_ACTION_ID}__{i}",
                "value": q["name"],
            },
        })

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": "*Select a query to run:*"}},
        *rows,
    ]
    return "Select a query to run:", blocks


def _run_response(
    query_name: str,
    queries: list[dict],
    jira,
    base_url: str,
    emoji_config: dict | None,
    timezone: str,
) -> tuple[str, list[dict]]:
    matches = [q for q in queries if q["name"].lower() == query_name.lower()]
    if not matches:
        available = ", ".join(f"`{q['name']}`" for q in queries)
        raise ValueError(f"Query '{query_name}' not found. Available: {available}")

    query_cfg = matches[0]
    effective_emoji_config = _merge_emoji_config(emoji_config, query_cfg.get("emojis"))
    fields = query_cfg.get("fields", ["key", "summary", "assignee", "status"])
    field_map = query_cfg.get("field_map") or {}
    tz = query_cfg.get("timezone", timezone)
    parent_fields = query_cfg.get("parent_fields") or []
    parent_field_map = query_cfg.get("parent_field_map") or {}

    issues = jira.search(
        jql=query_cfg["jql"],
        fields=fields,
        max_results=query_cfg.get("max_results", 50),
        field_map=field_map,
        extra_api_fields=["parent", "issuetype"] if parent_fields else None,
    )

    if parent_fields:
        _enrich_parent_fields(issues, jira, parent_fields, parent_field_map)

    display_fields = fields + [f"↑ {f}" for f in parent_fields]
    blocks = build_blocks(
        query_name=query_cfg["name"],
        issues=issues,
        base_url=base_url,
        fields=display_fields,
        emoji_config=effective_emoji_config,
        tz_name=tz,
    )
    fallback = f"{query_cfg['name']} — {len(issues)} issue(s) found"
    return fallback, blocks


def create_app(config: dict) -> App:
    app = App(token=config["slack"]["bot_token"])
    jira, _ = _make_clients(config)
    queries = config.get("queries", [])
    base_url = config["jira"]["base_url"]
    emoji_config = config.get("emojis")
    timezone = config.get("timezone", "UTC")

    @app.command("/runjql")
    def handle_runjql(ack, respond, command):  # pylint: disable=unused-variable
        ack()
        text = (command.get("text") or "").strip()

        if not text or text == "list":
            msg, blocks = _list_response(queries)
            respond(response_type="ephemeral", text=msg, **({"blocks": blocks} if blocks else {}))
            return

        if text.startswith("run "):
            query_name = text[4:].strip()
            try:
                fallback, blocks = _run_response(
                    query_name, queries, jira, base_url, emoji_config, timezone
                )
                respond(response_type="ephemeral", text=fallback, blocks=blocks)
            except ValueError as exc:
                respond(response_type="ephemeral", text=str(exc))
            return

        respond(
            response_type="ephemeral",
            text="Unknown subcommand. Usage: `/runjql list` or `/runjql run <query-name>`",
        )

    @app.action(re.compile(f"^{_RUN_QUERY_ACTION_ID}__\\d+$"))
    def handle_run_query(ack, body, respond):  # pylint: disable=unused-variable
        ack()
        query_name = body["actions"][0]["value"]
        try:
            fallback, blocks = _run_response(
                query_name, queries, jira, base_url, emoji_config, timezone
            )
            respond(response_type="ephemeral", text=fallback, blocks=blocks)
        except ValueError as exc:
            respond(response_type="ephemeral", text=str(exc))

    return app


def start_socket_mode(config: dict) -> None:
    app_token = os.environ["SLACK_APP_TOKEN"]
    app = create_app(config)
    handler = SocketModeHandler(app, app_token)
    print("Socket Mode server started. Press Ctrl+C to stop.")
    handler.start()
