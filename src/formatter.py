import re
import zoneinfo
from datetime import date as _date, datetime, timedelta, timezone

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


# Status -> emoji (matched case-insensitively on prefix/substring)
_STATUS_EMOJI = {
    "open":        ":white_circle:",
    "to do":       ":white_circle:",
    "backlog":     ":white_circle:",
    "in progress": ":large_blue_circle:",
    "in review":   ":large_yellow_circle:",
    "review":      ":large_yellow_circle:",
    "blocked":     ":red_circle:",
    "done":        ":white_check_mark:",
    "closed":      ":white_check_mark:",
    "resolved":    ":white_check_mark:",
    "cancelled":   ":x:",
    "won't fix":   ":x:",
}

# Priority -> emoji
_PRIORITY_EMOJI = {
    "blocker":  ":rotating_light:",
    "critical": ":rotating_light:",
    "high":     ":red_circle:",
    "medium":   ":large_yellow_circle:",
    "low":      ":large_blue_circle:",
    "lowest":   ":white_circle:",
    "trivial":  ":white_circle:",
}

# Issue type -> emoji
_TYPE_EMOJI = {
    "bug":         ":bug:",
    "story":       ":book:",
    "task":        ":ballot_box_with_check:",
    "epic":        ":zap:",
    "subtask":     ":small_blue_diamond:",
    "improvement": ":sparkles:",
    "feature":     ":sparkles:",
}


_KNOWN_FIELDS = {"key", "summary", "assignee", "status", "priority", "reporter", "issuetype"}


def _format_date_relative(iso: str, tz_name: str = "UTC") -> str:
    """Return a human-friendly relative label for a date string.

    Future (>=2 days): "Xd"
    Today (0 days):   "Xh" until midnight in the configured timezone
    Past:             "Mar 5" style (so overdue dates are visually distinct)
    """
    try:
        target = _date.fromisoformat(iso[:10])
    except (ValueError, TypeError):
        return iso

    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except (zoneinfo.ZoneInfoNotFoundError, KeyError):
        tz = timezone.utc

    now_local = datetime.now(tz)
    today = now_local.date()
    delta = (target - today).days

    if delta > 0:
        return f"{delta}d"
    if delta == 0:
        midnight = datetime(today.year, today.month, today.day, tzinfo=tz) + timedelta(days=1)
        hours_left = int((midnight - now_local).total_seconds() // 3600)
        return f"{hours_left}h"
    return target.strftime("%b %-d")


def _normalize_emoji_map(raw: dict | None) -> dict:
    """Lower-case all keys so YAML authors don't need to worry about case."""
    if not raw:
        return {}
    return {k.lower(): v for k, v in raw.items()}


def _status_emoji(status: str, overrides: dict | None = None) -> str:
    mapping = {**_STATUS_EMOJI, **(overrides or {})}
    key = status.lower()
    for k, v in mapping.items():
        if key == k or key.startswith(k):
            return v
    return ":black_circle:"


def _priority_emoji(priority: str, overrides: dict | None = None) -> str:
    mapping = {**_PRIORITY_EMOJI, **(overrides or {})}
    return mapping.get(priority.lower(), ":black_circle:")


def _type_emoji(issuetype: str, overrides: dict | None = None) -> str:
    mapping = {**_TYPE_EMOJI, **(overrides or {})}
    return mapping.get(issuetype.lower(), ":page_facing_up:")


def build_blocks(
    query_name: str,
    issues: list[dict],
    base_url: str,
    fields: list[str],
    emoji_config: dict | None = None,
    tz_name: str = "UTC",
) -> list[dict]:
    emoji_cfg = emoji_config or {}
    status_ov = _normalize_emoji_map(emoji_cfg.get("status"))
    priority_ov = _normalize_emoji_map(emoji_cfg.get("priority"))
    type_ov = _normalize_emoji_map(emoji_cfg.get("type"))
    header_emoji = emoji_cfg.get("header", ":jira:")

    count = len(issues)
    base_url = base_url.rstrip("/")
    blocks: list[dict] = []

    # -- Header ----------------------------------------------------------------
    header_text = f"{header_emoji} {query_name}" if header_emoji else query_name
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": header_text, "emoji": True},
    })

    # -- Summary bar -----------------------------------------------------------
    if count == 0:
        summary = ":white_check_mark:  No issues found - all clear!"
    elif count == 1:
        summary = ":mag:  *1 issue* matched"
    else:
        summary = f":mag:  *{count} issues* matched"

    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": summary},
    })

    if count == 0:
        blocks.append({"type": "divider"})
        blocks.append(_footer())
        return blocks

    blocks.append({"type": "divider"})

    # -- Issue list (one full-width section per issue) -------------------------
    for issue in issues:
        blocks.append(_issue_block(issue, base_url, fields, status_ov, priority_ov, type_ov, tz_name))

    # -- Footer ----------------------------------------------------------------
    blocks.append({"type": "divider"})
    blocks.append(_footer(base_url))
    return blocks


def _issue_block(
    issue: dict,
    base_url: str,
    fields: list[str],
    status_overrides: dict | None = None,
    priority_overrides: dict | None = None,
    type_overrides: dict | None = None,
    tz_name: str = "UTC",
) -> dict:
    key = issue["key"]
    url = f"{base_url}/browse/{key}"
    summary = issue.get("summary", "(no summary)")
    if len(summary) > 120:
        summary = summary[:117] + "…"

    issuetype = issue.get("issuetype", "")
    type_icon = f"{_type_emoji(issuetype, type_overrides)}  " if issuetype else ""
    line1 = f"{type_icon}*<{url}|{key}>*  {summary}"

    # Build labeled field items for two-column grid display
    field_items: list[dict] = []
    if "status" in fields:
        status = issue.get("status", "Unknown")
        field_items.append({
            "type": "mrkdwn",
            "text": f"*Status:*\n{_status_emoji(status, status_overrides)} {status}",
        })
    if "priority" in fields:
        priority = issue.get("priority", "")
        if priority:
            field_items.append({
                "type": "mrkdwn",
                "text": f"*Priority:*\n{_priority_emoji(priority, priority_overrides)} {priority}",
            })
    if "assignee" in fields:
        field_items.append({
            "type": "mrkdwn",
            "text": f"*Assignee:*\n{issue.get('assignee', 'Unassigned')}",
        })
    if "duedate" in fields:
        val = issue.get("duedate", "")
        if val:
            field_items.append({
                "type": "mrkdwn",
                "text": f"*Due:*\n:calendar: {_format_date_relative(val, tz_name)}",
            })
    for field_name in fields:
        if field_name in _KNOWN_FIELDS or field_name == "duedate":
            continue
        val = issue.get(field_name, "")
        if not val:
            continue
        if _ISO_DATE.match(str(val)):
            field_items.append({
                "type": "mrkdwn",
                "text": f"*{field_name}:*\n:calendar: {_format_date_relative(str(val), tz_name)}",
            })
        else:
            field_items.append({"type": "mrkdwn", "text": f"*{field_name}:*\n{val}"})

    block: dict = {"type": "section", "text": {"type": "mrkdwn", "text": line1}}
    if field_items:
        block["fields"] = field_items[:10]  # Slack max 10 fields per section
    return block


def _footer(base_url: str = "") -> dict:
    ts = datetime.now(timezone.utc).strftime("%b %-d, %Y at %H:%M UTC")
    text = f":clock3:  {ts}"
    if base_url:
        text += f"  ·  <{base_url}|Open Jira>"
    return {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": text}],
    }
