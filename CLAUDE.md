# CLAUDE.md — slack-notifications

## Purpose

Python CLI tool that runs named JQL searches against Jira Cloud and posts formatted Slack Block Kit messages to configured channels. Supports one-shot runs and a persistent cron scheduler daemon.

## Directory layout

```
slack-notifications/
|-- config/queries.yaml        # All config: Jira/Slack settings, named queries
|-- src/
|      |-- jira_client.py         # Jira Cloud REST API v3 wrapper
|      |-- slack_client.py        # Slack Web API (chat.postMessage)
|      |-- formatter.py           # Block Kit message builder
|      |-- runner.py              # Orchestration: load → query → format → post
|-- tests/                     # pytest suite (fully mocked, no real network)
|-- main.py                    # CLI entrypoint (argparse)
|-- Makefile                   # Dev tasks (setup, run, lint, test, …)
|-- requirements.txt
|-- .pylintrc                  # Pylint config (target: 10/10)
|-- .editorconfig              # UTF-8, LF, per-type indent
|-- .gitattributes             # Git line-ending normalization
|-- slack-app-manifest.yaml    # Import to create the Slack app
```

## Make targets

```
make setup                     # Create .venv and install dependencies
make list                      # Print all configured query names
make run                       # Run all queries, post to Slack
make query QUERY="Name"        # Run a single named query
make schedule                  # Start the APScheduler daemon
make lint                      # Run pylint (src/ + main.py)
make test                      # Run pytest
make clean                     # Remove .venv
```

## CLI flags

```
python main.py --config /other/path.yaml run   # use alternate config file
python main.py --debug run                     # verbose Jira HTTP logging
```

## Architecture

```
main.py (argparse)
  |-- runner.py
        |-- load_config()       # parse YAML + inject env var secrets
        |-- JiraClient.search() # GET /rest/api/3/search/jql
        |-- build_blocks()      # formatter.py → Block Kit JSON
        |-- SlackClient.post_message()  # chat.postMessage
```

## Config format (config/queries.yaml)

```yaml
jira:
  base_url: https://yourcompany.atlassian.net
  email: user@example.com
  # JIRA_API_TOKEN read from env

slack:
  # SLACK_BOT_TOKEN read from env

timezone: America/Los_Angeles   # IANA tz, global default

emojis:                         # all optional overrides
  header: ":bell:"
  status:
    "In Progress": ":arrows_counterclockwise:"
  priority:
    "P0": ":rotating_light:"
  type:
    "Change Request": ":memo:"

queries:
  - name: Open CDS CRs
    jql: "project=CR AND status not in ('Done')"
    channel: "#my-channel"
    max_results: 20
    schedule: "0 9 * * 1-5"    # 5-field cron, optional
    timezone: America/New_York  # per-query override, optional
    fields:
      - key
      - summary
      - assignee
      - status
      - priority
      - duedate
      - My Custom Field         # display name (use field_map to resolve)
    field_map:
      'My Custom Field': customfield_10102   # run --debug to find IDs
```

**Built-in fields:** `key`, `summary`, `assignee`, `status`, `priority`, `issuetype`, `reporter`, `duedate`

**Custom fields:** list display name in `fields`, map it to the Jira field ID in `field_map`. Run `python main.py --debug run` to see raw field keys in Jira responses.

**Date fields:** Any value matching `YYYY-MM-DD` is rendered as a relative label — `"5d"` (future), `"3h"` (due today, hours to midnight), or `"Mar 5"` (past/overdue).

## Secrets

```
JIRA_API_TOKEN   Jira Cloud API token (Basic auth with email)
SLACK_BOT_TOKEN  Slack bot token (xoxb-…)
```

Never committed — injected at runtime from `.env` (via python-dotenv) or the environment.

## Slack message structure

One message per query:
1. `header` block — query name with configurable emoji
2. `section` — issue count summary
3. `divider`
4. One full-width `section` per issue — linked key, summary, status/priority/assignee/date metadata
5. `divider`
6. `context` footer — timestamp + "Open Jira" link

## Code conventions

- Python 3.12+, UTF-8 everywhere (`encoding="utf-8"` on all `open()` calls)
- LF line endings (.editorconfig + .gitattributes)
- 4-space indent for Python, 2-space for YAML
- Max line length: 120 chars (pylint enforced)
- Pylint score must stay at 10.00/10 (`make lint`)
- No docstrings required (disabled in .pylintrc)
- No type annotations on internal helpers; use `dict | None` union syntax where needed

## Testing

```
make test                  # run full suite
.venv/bin/pytest tests/ -v # directly
```

- All tests in `tests/` — zero real network calls; Jira and Slack are fully mocked
- Issue sections in formatter tests are identified by filtering blocks whose `text.text` contains `/browse/`
- `test_runner.py` uses `MINIMAL_YAML` fixture with a real query definition to exercise config loading

## Scheduler

Uses APScheduler 3.x (`BlockingScheduler` + `CronTrigger.from_crontab()`). Each query's `schedule:` is a standard 5-field cron expression. The global `timezone:` (or per-query override) is passed to `CronTrigger`. Queries without a `schedule:` field are skipped in daemon mode.
