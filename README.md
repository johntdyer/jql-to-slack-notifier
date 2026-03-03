# jql-to-slack-notifier

[![CI](https://github.com/johntdyer/jql-to-slack-notifier/actions/workflows/ci.yml/badge.svg)](https://github.com/johntdyer/jql-to-slack-notifier/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/johntdyer/jql-to-slack-notifier/graph/badge.svg)](https://codecov.io/gh/johntdyer/jql-to-slack-notifier)
[![Python](https://img.shields.io/badge/python-3.11_%7C_3.12_%7C_3.13-blue)](https://www.python.org)
[![Pylint](https://img.shields.io/badge/pylint-10%2F10-brightgreen)](https://pylint.readthedocs.io)
[![Container](https://img.shields.io/github/v/release/johntdyer/jql-to-slack-notifier?label=ghcr&logo=docker&color=blue)](https://github.com/johntdyer/jql-to-slack-notifier/pkgs/container/jql-to-slack-notifier)
[![Helm](https://img.shields.io/github/v/release/johntdyer/jql-to-slack-notifier?label=helm&logo=helm&color=blue)](https://github.com/johntdyer/jql-to-slack-notifier/pkgs/container/charts%2Fjql-to-slack-notifier)

Runs JQL searches against Jira Cloud and posts pretty-formatted messages to Slack using Block Kit.

## Message format

Each query produces a Slack message like this:

```
+-------------------------------------------------------------+
|  :bell:  Items Due This Week                                |
+-------------------------------------------------------------+
:mag:  *4 issues* matched

-------------------------------------------------------------

:memo:  *PLAT-1042*  Migrate auth service to OAuth 2.0
:large_blue_circle: In Progress  |  :large_yellow_circle: Medium  |  :bust_in_silhouette: Jane Smith  |  :calendar: Due 3d

:fire:  *CR-88*  Emergency DB failover procedure
:white_circle: Open  |  :rotating_light: P0  |  :bust_in_silhouette: Unassigned  |  :calendar: Due 5h

:fire:  *CR-91*  Rotate prod API keys after breach
:arrows_counterclockwise: In Progress  |  :red_circle: P1  |  :bust_in_silhouette: Alex Torres  |  :calendar: Due 2d

:memo:  *PLAT-999*  Update runbook for cache invalidation
:white_circle: Open  |  :large_yellow_circle: Medium  |  :bust_in_silhouette: Unassigned  |  :calendar: Mar 1

-------------------------------------------------------------
:clock3:  Mar 2, 2026 at 09:00 UTC  |  Open Jira
```

### Date display

Due dates and custom date fields render as relative labels:

| Value   | Meaning |
|---------|---------|
| `5d`    | due in 5 days |
| `3h`    | due today, ~3 hours to midnight in the configured timezone |
| `Mar 1` | past due -- shown as a fixed date so overdue items stand out |

### Emoji reference

Built-in defaults. All mappings are case-insensitive and can be overridden in `config/queries.yaml`.

| Category | Slack emoji | Status / value |
|----------|-------------|----------------|
| Status | `:white_circle:` | Open, To Do, Backlog |
| | `:large_blue_circle:` | In Progress |
| | `:large_yellow_circle:` | In Review, Review |
| | `:red_circle:` | Blocked |
| | `:white_check_mark:` | Done, Closed, Resolved |
| | `:x:` | Cancelled, Won't Fix |
| Priority | `:rotating_light:` | Blocker, Critical |
| | `:red_circle:` | High |
| | `:large_yellow_circle:` | Medium |
| | `:large_blue_circle:` | Low |
| | `:white_circle:` | Lowest, Trivial |
| Type | `:bug:` | Bug |
| | `:book:` | Story |
| | `:ballot_box_with_check:` | Task |
| | `:zap:` | Epic |
| | `:small_blue_diamond:` | Sub-task |
| | `:sparkles:` | Improvement, Feature |

---

## Setup

### 1. Install dependencies

```bash
make setup
```

Creates a `.venv` virtual environment, installs all dependencies, and copies `.env.example` -> `.env` if it does not already exist.

### 2. Create a Jira API token

1. Go to [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click **Create API token**, give it a label (e.g. `jql-notifications`)
3. Copy the token -- you won't be able to see it again

### 3. Create the Slack app

This repo includes a pre-configured app manifest so you don't have to manually set up scopes.

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App**
2. Choose **From a manifest**
3. Select your workspace and click **Next**
4. Switch to the **YAML** tab, paste the contents of [`slack-app-manifest.yaml`](slack-app-manifest.yaml), then click **Next** -> **Create**
5. On the app page, go to **OAuth & Permissions** and click **Install to Workspace** -> **Allow**
6. Copy the **Bot User OAuth Token** (starts with `xoxb-`)
7. Invite the bot to each channel it should post in: `/invite @JQL Notifications`

### 4. Configure secrets

```bash
cp .env.example .env
```

Edit `.env` with the tokens from steps 2 and 3:

```env
JIRA_API_TOKEN=your_jira_api_token
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
```

The script reads `.env` automatically -- no `export` or shell setup needed.

> **Note:** Never commit `.env` to source control -- it contains secrets.

### 5. Configure queries

Edit `config/queries.yaml`. At minimum you need `jira.base_url`, `jira.email`, and at least one query:

```yaml
jira:
  base_url: https://yourcompany.atlassian.net
  email: you@example.com
  # JIRA_API_TOKEN read from env

slack:
  # SLACK_BOT_TOKEN read from env

timezone: America/Los_Angeles   # IANA tz name, global default

queries:
  - name: Open Critical Bugs
    jql: "priority = Critical AND status != Done ORDER BY created DESC"
    channel: "#engineering"
    max_results: 20
    schedule: "0 9 * * 1-5"    # 5-field cron - 9:00 AM Mon-Fri
    fields:
      - key
      - summary
      - assignee
      - status
      - priority
      - duedate
```

**Built-in fields:** `key`, `summary`, `assignee`, `status`, `priority`, `issuetype`, `reporter`, `duedate`

**Custom fields:** add the display name to `fields` and map it to the Jira field ID in `field_map`. Run
`python main.py --debug run` to see raw field IDs in API responses.

```yaml
fields:
  - key
  - summary
  - Target End Date          # display name
field_map:
  'Target End Date': customfield_10102
```

---

## Emoji configuration

Emoji mappings can be set globally (applies to every query) and overridden per query. Keys are
matched case-insensitively. Per-query values are merged on top of global ones -- you only need
to list what differs.

### Global emoji config

Place an `emojis:` block at the top level of `config/queries.yaml`. These values apply to every
query unless a query overrides them.

```yaml
# config/queries.yaml

emojis:
  header: ":bell:"        # shown before the query name in the header block
                          # set to "" to omit; use ":jira:" after importing icons/jira-emoji.svg
  status:
    "Accepted":  ":white_check_mark:"
    "Discarded": ":wastebasket:"
    "In Progress": ":arrows_counterclockwise:"
    "Ready":     ":large_green_circle:"

  priority:
    "P0": ":rotating_light:"
    "P1": ":red_circle:"
    "P2": ":large_yellow_circle:"

  type:
    "Change Request": ":memo:"
    "Incident":       ":fire:"
    "Feature":        ":heavy_dollar_sign:"

queries:
  - name: Open Critical Bugs
    jql: "priority = Critical AND status != Done"
    channel: "#engineering"
    fields: [key, summary, status, priority]
```

### Per-query emoji overrides

Add an `emojis:` block inside any individual query. Per-query entries are merged on top of the
global config -- you only need to specify the values that differ for that query.

```yaml
# config/queries.yaml

emojis:                           # global defaults
  header: ":bell:"
  status:
    "In Progress": ":arrows_counterclockwise:"
  priority:
    "P0": ":rotating_light:"
    "P1": ":red_circle:"

queries:
  - name: Open Critical Bugs      # uses global emojis, no overrides
    jql: "priority = Critical AND status != Done"
    channel: "#engineering"
    fields: [key, summary, status, priority]

  - name: Incident Board          # overrides header and one status emoji for this query only
    jql: "issuetype = Incident AND status != Done"
    channel: "#incidents"
    fields: [key, summary, status, assignee]
    emojis:
      header: ":rotating_light:"  # overrides global ":bell:" for this query
      status:
        "Investigating": ":mag:"  # adds a new status; other status emojis from global still apply
        "Mitigated":     ":large_yellow_circle:"
        "Resolved":      ":white_check_mark:"
```

### Matching rules

| Category | Match type | Example |
|----------|-----------|---------|
| `status` | Prefix (case-insensitive) | `"In Progress"` matches `"In Progress (Dev)"` |
| `priority` | Exact (case-insensitive) | `"P0"` only matches `"P0"` |
| `type` | Exact (case-insensitive) | `"Incident"` only matches `"Incident"` |

Unrecognised values fall back to `:black_circle:` (status/priority) or `:page_facing_up:` (type).

---

## Usage

```bash
make list                          # list all configured queries
make run                           # run all queries and post to Slack
make query QUERY="Open CDS CR's"   # run a single query by name
make schedule                      # start the APScheduler daemon
```

Or use Python directly (venv must be active or use `.venv/bin/python`):

```bash
python main.py run --query "Open CDS CR's"
python main.py --config /path/to/other.yaml run
python main.py --debug run         # verbose Jira HTTP logging
```

### Schedule syntax

The `schedule:` field in each query uses standard **5-field cron syntax**:

```text
# MIN  HOUR  DOM  MONTH  DOW
  0    9     *    *      1-5    -> 9:00 AM Monday-Friday
  30   8     *    *      *      -> 8:30 AM every day
  0    8,17  *    *      *      -> 8:00 AM and 5:00 PM every day
```

The timezone is taken from the query's `timezone:` key, falling back to the global `timezone:`
(default: `UTC`).

---

## Kubernetes / Helm

The container image is published to GHCR and a Helm chart is published as an OCI artifact on every
tagged release.

### Install with Helm

```bash
# Pull values template
helm show values oci://ghcr.io/johntdyer/charts/jql-to-slack-notifier \
  --version 1.0.0 > my-values.yaml
```

Edit `my-values.yaml` -- paste your `queries.yaml` content into the `config:` key and fill in
secrets:

```yaml
secrets:
  jiraApiToken: "your-jira-api-token"
  slackBotToken: "xoxb-your-slack-bot-token"

config: |
  jira:
    base_url: https://yourcompany.atlassian.net
    email: you@example.com
  slack: {}
  timezone: America/Los_Angeles
  queries:
    - name: Open Critical Bugs
      jql: "priority = Critical AND status != Done"
      channel: "#engineering"
      schedule: "0 9 * * 1-5"
      fields: [key, summary, assignee, status, priority]
```

```bash
helm install jql-notifier oci://ghcr.io/johntdyer/charts/jql-to-slack-notifier \
  --version 1.0.0 \
  -f my-values.yaml
```

### Use an existing Kubernetes secret

If you manage secrets externally (e.g. via Vault or ESO), create a secret with keys
`JIRA_API_TOKEN` and `SLACK_BOT_TOKEN`, then reference it:

```bash
kubectl create secret generic jql-notifier-secrets \
  --from-literal=JIRA_API_TOKEN=... \
  --from-literal=SLACK_BOT_TOKEN=xoxb-...

helm install jql-notifier oci://ghcr.io/johntdyer/charts/jql-to-slack-notifier \
  --version 1.0.0 \
  --set existingSecret=jql-notifier-secrets \
  -f my-values.yaml
```

### Run with Docker

```bash
docker run --rm \
  -e JIRA_API_TOKEN=... \
  -e SLACK_BOT_TOKEN=xoxb-... \
  -v "$PWD/config:/app/config:ro" \
  ghcr.io/johntdyer/jql-to-slack-notifier:latest \
  python main.py run
```

---

## Testing

```bash
make test
```

Tests cover all four modules and make no real network calls -- Jira and Slack APIs are fully mocked.

| File | What's tested |
|------|--------------|
| `tests/test_formatter.py` | Emoji mapping, Block Kit structure, date formatting, truncation |
| `tests/test_jira_client.py` | API URL, auth, field normalization, error handling |
| `tests/test_slack_client.py` | Payload shape, auth header, API error handling |
| `tests/test_runner.py` | Config loading, env var injection, query name matching |

---

## Project structure

```
jql-to-slack-notifier/
  charts/
    jql-to-slack-notifier/     Helm chart (published to GHCR OCI on release)
      Chart.yaml
      values.yaml
      templates/
  config/
    queries.yaml               JQL queries, channels, schedule times
  src/
    jira_client.py             Jira Cloud REST API v3
    slack_client.py            Slack Web API (chat.postMessage)
    formatter.py               Block Kit message builder
    runner.py                  Orchestration
  tests/
    test_formatter.py
    test_jira_client.py
    test_slack_client.py
    test_runner.py
  .github/
    workflows/ci.yml           CI: lint, test, docker build, helm publish
  icons/
    bot-icon.svg               Bot avatar (upload in Slack app settings)
    jira-emoji.svg             Optional :jira: custom emoji
  Dockerfile
  main.py                      CLI entrypoint
  Makefile
  slack-app-manifest.yaml      Import this to create the Slack app
  requirements.txt
  .env.example
```
