import pytest
from src.formatter import build_blocks, _status_emoji, _priority_emoji, _type_emoji

BASE_URL = "https://company.atlassian.net"
FIELDS = ["key", "summary", "assignee", "status", "priority"]


def _issue(**kwargs):
    defaults = {
        "key": "PROJ-1",
        "summary": "Test issue",
        "assignee": "Jane Smith",
        "status": "In Progress",
        "priority": "High",
    }
    return {**defaults, **kwargs}


# -- Emoji helpers ------------------------------------------------------------

class TestStatusEmoji:
    def test_in_progress(self):
        assert _status_emoji("In Progress") == ":large_blue_circle:"

    def test_done(self):
        assert _status_emoji("Done") == ":white_check_mark:"

    def test_open(self):
        assert _status_emoji("Open") == ":white_circle:"

    def test_blocked(self):
        assert _status_emoji("Blocked") == ":red_circle:"

    def test_in_review(self):
        assert _status_emoji("In Review") == ":large_yellow_circle:"

    def test_cancelled(self):
        assert _status_emoji("Cancelled") == ":x:"

    def test_case_insensitive(self):
        assert _status_emoji("IN PROGRESS") == _status_emoji("in progress")

    def test_unknown_status(self):
        assert _status_emoji("Weird Custom Status") == ":black_circle:"


class TestPriorityEmoji:
    def test_critical(self):
        assert _priority_emoji("Critical") == ":rotating_light:"

    def test_blocker(self):
        assert _priority_emoji("Blocker") == ":rotating_light:"

    def test_high(self):
        assert _priority_emoji("High") == ":red_circle:"

    def test_medium(self):
        assert _priority_emoji("Medium") == ":large_yellow_circle:"

    def test_low(self):
        assert _priority_emoji("Low") == ":large_blue_circle:"

    def test_unknown_priority(self):
        assert _priority_emoji("Unknown") == ":black_circle:"


class TestTypeEmoji:
    def test_bug(self):
        assert _type_emoji("Bug") == ":bug:"

    def test_story(self):
        assert _type_emoji("Story") == ":book:"

    def test_epic(self):
        assert _type_emoji("Epic") == ":zap:"

    def test_task(self):
        assert _type_emoji("Task") == ":ballot_box_with_check:"

    def test_unknown_type(self):
        assert _type_emoji("Unknown") == ":page_facing_up:"


# -- build_blocks -------------------------------------------------------------

class TestBuildBlocks:
    def test_no_issues_returns_all_clear(self):
        blocks = build_blocks("My Query", [], BASE_URL, FIELDS)
        header = blocks[0]
        assert header["type"] == "header"
        assert "My Query" in header["text"]["text"]

        summary = blocks[1]
        assert "No issues found" in summary["text"]["text"]

    def test_no_issues_has_no_issue_rows(self):
        blocks = build_blocks("My Query", [], BASE_URL, FIELDS)
        section_types = [b["type"] for b in blocks]
        # Should only have: header, section (summary), divider, context (footer)
        assert section_types.count("section") == 1

    def test_single_issue_singular_wording(self):
        blocks = build_blocks("My Query", [_issue()], BASE_URL, FIELDS)
        summary = blocks[1]
        assert "*1 issue*" in summary["text"]["text"]

    def test_multiple_issues_plural_wording(self):
        issues = [_issue(key=f"PROJ-{i}") for i in range(3)]
        blocks = build_blocks("My Query", issues, BASE_URL, FIELDS)
        summary = blocks[1]
        assert "*3 issues*" in summary["text"]["text"]

    def _issue_blocks(self, blocks):
        """Section blocks that represent individual issues (contain a /browse/ link)."""
        return [
            b for b in blocks
            if b["type"] == "section" and "/browse/" in b.get("text", {}).get("text", "")
        ]

    def test_issue_link_in_block(self):
        blocks = build_blocks("My Query", [_issue(key="PROJ-42")], BASE_URL, FIELDS)
        issue_blocks = self._issue_blocks(blocks)
        assert issue_blocks, "Expected at least one issue section block"
        text = issue_blocks[0]["text"]["text"]
        assert "PROJ-42" in text
        assert f"{BASE_URL}/browse/PROJ-42" in text

    def test_long_summary_truncated(self):
        long_summary = "A" * 117 + "UNIQUE_TAIL"
        blocks = build_blocks("My Query", [_issue(summary=long_summary)], BASE_URL, FIELDS)
        text = self._issue_blocks(blocks)[0]["text"]["text"]
        assert "…" in text
        assert "UNIQUE_TAIL" not in text

    def test_one_section_block_per_issue(self):
        issues = [_issue(key=f"PROJ-{i}") for i in range(12)]
        blocks = build_blocks("My Query", issues, BASE_URL, FIELDS)
        assert len(self._issue_blocks(blocks)) == 12

    def test_footer_is_context_block(self):
        blocks = build_blocks("My Query", [_issue()], BASE_URL, FIELDS)
        assert blocks[-1]["type"] == "context"

    def test_footer_contains_open_jira_link(self):
        blocks = build_blocks("My Query", [_issue()], BASE_URL, FIELDS)
        footer_text = blocks[-1]["elements"][0]["text"]
        assert BASE_URL in footer_text

    def test_shows_status_emoji(self):
        blocks = build_blocks("My Query", [_issue(status="Done")], BASE_URL, FIELDS)
        text = self._issue_blocks(blocks)[0]["text"]["text"]
        assert ":white_check_mark:" in text
        assert "Done" in text

    def test_shows_priority_emoji(self):
        blocks = build_blocks("My Query", [_issue(priority="Critical")], BASE_URL, FIELDS)
        text = self._issue_blocks(blocks)[0]["text"]["text"]
        assert ":rotating_light:" in text

    def test_shows_assignee(self):
        blocks = build_blocks("My Query", [_issue(assignee="Bob Lee")], BASE_URL, FIELDS)
        text = self._issue_blocks(blocks)[0]["text"]["text"]
        assert "Bob Lee" in text

    def test_omits_priority_when_not_in_fields(self):
        fields = ["key", "summary", "status"]
        blocks = build_blocks("My Query", [_issue()], BASE_URL, fields)
        text = self._issue_blocks(blocks)[0]["text"]["text"]
        assert ":rotating_light:" not in text
        assert ":red_circle:" not in text


# -- Emoji config overrides ---------------------------------------------------

class TestEmojiConfigOverrides:
    def test_status_override_replaces_default(self):
        overrides = {"in progress": ":arrows_counterclockwise:"}
        assert _status_emoji("In Progress", overrides) == ":arrows_counterclockwise:"

    def test_status_override_adds_new_status(self):
        overrides = {"accepted": ":party_popper:"}
        assert _status_emoji("Accepted", overrides) == ":party_popper:"

    def test_status_override_keys_are_case_insensitive(self):
        overrides = {"In Progress": ":fire:"}
        # overrides keys passed through _normalize_emoji_map are lowercased before lookup
        from src.formatter import _normalize_emoji_map
        normalized = _normalize_emoji_map({"In Progress": ":fire:"})
        assert _status_emoji("In Progress", normalized) == ":fire:"

    def test_priority_override_replaces_default(self):
        overrides = {"high": ":fire:"}
        assert _priority_emoji("High", overrides) == ":fire:"

    def test_priority_override_adds_new_value(self):
        overrides = {"p0": ":rotating_light:"}
        assert _priority_emoji("P0", overrides) == ":rotating_light:"

    def test_type_override_adds_new_type(self):
        overrides = {"change request": ":memo:"}
        assert _type_emoji("Change Request", overrides) == ":memo:"

    def test_type_override_replaces_default(self):
        overrides = {"bug": ":lady_beetle:"}
        assert _type_emoji("Bug", overrides) == ":lady_beetle:"

    def _issue_text(self, blocks):
        return next(
            b["text"]["text"] for b in blocks
            if b["type"] == "section" and "/browse/" in b.get("text", {}).get("text", "")
        )

    def test_build_blocks_uses_status_override(self):
        issue = _issue(status="In Progress")
        emoji_config = {"status": {"In Progress": ":fire:"}}
        blocks = build_blocks("Q", [issue], BASE_URL, FIELDS, emoji_config=emoji_config)
        text = self._issue_text(blocks)
        assert ":fire:" in text
        assert ":large_blue_circle:" not in text

    def test_build_blocks_uses_priority_override(self):
        issue = _issue(priority="High")
        emoji_config = {"priority": {"High": ":fire:"}}
        blocks = build_blocks("Q", [issue], BASE_URL, FIELDS, emoji_config=emoji_config)
        text = self._issue_text(blocks)
        assert ":fire:" in text
        assert ":red_circle:" not in text

    def test_build_blocks_no_emoji_config_uses_defaults(self):
        issue = _issue(status="Done")
        blocks = build_blocks("Q", [issue], BASE_URL, FIELDS)
        text = self._issue_text(blocks)
        assert ":white_check_mark:" in text
