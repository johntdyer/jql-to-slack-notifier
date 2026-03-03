import os
import yaml
from dotenv import load_dotenv

from .jira_client import JiraClient
from .slack_client import SlackClient
from .formatter import build_blocks


def load_config(path: str = "config/queries.yaml") -> dict:
    load_dotenv()
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Inject secrets from environment
    # Use `or {}` to handle keys that exist in YAML but have only comments (parsed as None)
    config["jira"] = config.get("jira") or {}
    config["slack"] = config.get("slack") or {}
    config["jira"]["api_token"] = os.environ["JIRA_API_TOKEN"]
    config["slack"]["bot_token"] = os.environ["SLACK_BOT_TOKEN"]

    return config


def _make_clients(config: dict) -> tuple[JiraClient, SlackClient]:
    jira = JiraClient(
        base_url=config["jira"]["base_url"],
        email=config["jira"]["email"],
        api_token=config["jira"]["api_token"],
    )
    slack = SlackClient(bot_token=config["slack"]["bot_token"])
    return jira, slack


def _merge_emoji_config(global_cfg: dict | None, query_cfg: dict | None) -> dict | None:
    if not query_cfg:
        return global_cfg
    if not global_cfg:
        return query_cfg
    merged = dict(global_cfg)
    for key in ("status", "priority", "type"):
        if key in query_cfg:
            merged[key] = {**(global_cfg.get(key) or {}), **query_cfg[key]}
    if "header" in query_cfg:
        merged["header"] = query_cfg["header"]
    return merged


def run_query(
    query_cfg: dict,
    jira: JiraClient,
    slack: SlackClient,
    base_url: str,
    emoji_config: dict | None = None,
    timezone: str = "UTC",
) -> None:
    name = query_cfg["name"]
    jql = query_cfg["jql"]
    channel = query_cfg["channel"]
    max_results = query_cfg.get("max_results", 50)
    fields = query_cfg.get("fields", ["key", "summary", "assignee", "status"])
    # Per-query timezone overrides the global default
    tz = query_cfg.get("timezone", timezone)
    # Per-query emojis are merged on top of global emojis
    effective_emoji_config = _merge_emoji_config(emoji_config, query_cfg.get("emojis"))

    field_map = query_cfg.get("field_map") or {}
    print(f"  Running: {name}")
    issues = jira.search(jql=jql, fields=fields, max_results=max_results, field_map=field_map)
    print(f"  Found {len(issues)} issue(s)")

    blocks = build_blocks(
        query_name=name,
        issues=issues,
        base_url=base_url,
        fields=fields,
        emoji_config=effective_emoji_config,
        tz_name=tz,
    )
    fallback_text = f"{name} — {len(issues)} issue(s) found"
    slack.post_message(channel=channel, blocks=blocks, text=fallback_text)
    print(f"  Posted to {channel}")


def run_all(config: dict) -> None:
    jira, slack = _make_clients(config)
    base_url = config["jira"]["base_url"]
    emoji_config = config.get("emojis")
    timezone = config.get("timezone", "UTC")
    queries = config.get("queries", [])
    print(f"Running {len(queries)} query/queries...")
    for query_cfg in queries:
        run_query(query_cfg, jira, slack, base_url, emoji_config, timezone)


def run_named(config: dict, name: str) -> None:
    queries = config.get("queries", [])
    matches = [q for q in queries if q["name"].lower() == name.lower()]
    if not matches:
        available = [q["name"] for q in queries]
        raise ValueError(
            f"Query '{name}' not found. Available: {available}"
        )
    jira, slack = _make_clients(config)
    base_url = config["jira"]["base_url"]
    emoji_config = config.get("emojis")
    timezone = config.get("timezone", "UTC")
    run_query(matches[0], jira, slack, base_url, emoji_config, timezone)
