# jql-to-slack-notifier

[![CI](https://github.com/johntdyer/jql-to-slack-notifier/actions/workflows/ci.yml/badge.svg)](https://github.com/johntdyer/jql-to-slack-notifier/actions/workflows/ci.yml)

Runs JQL searches against Jira Cloud and posts pretty-formatted messages to Slack using Block Kit.

## Message format

Each query produces a Slack message like this:

```
┌──────────────────────────────────────┐
│  🎯  Open CDS CR's                   │  ← large header block
└──────────────────────────────────────┘
🔍  *5 issues* matched

──────────────────────────────────────────────────────────────

🐛 *PROJ-42*  Fix login on Safari        🔵  In Progress
                                          🚨 Critical  ·  👤 Jane Smith

🐛 *PROJ-38*  Payment timeout error      ⚪  Open
                                          🚨 Critical  ·  👤 Unassigned

──────────────────────────────────────────────────────────────
🕐  Mar 2, 2026 at 09:00 UTC  ·  Open Jira
```

Status emojis: 🔵 In Progress · 🟡 In Review · ✅ Done · 🔴 Blocked · ⚪ Open
Priority emojis: 🚨 Critical/Blocker · 🔴 High · 🟡 Medium · 🔵 Low
Type emojis: 🐛 Bug · 📖 Story · ✅ Task · ⚡ Epic

---

## Setup

### 1. Install dependencies

```bash
make setup
```

This creates a `.venv` virtual environment, installs all dependencies, and copies `.env.example` → `.env` if it doesn't already exist.

### 2. Create a Jira API token

1. Go to [https://id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click **Create API token**, give it a label (e.g. `jql-notifications`)
3. Copy the token — you won't be able to see it again

### 3. Create the Slack app

This repo includes a pre-configured app manifest so you don't have to manually set up scopes.

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps) and click **Create New App**
2. Choose **From a manifest**
3. Select your workspace and click **Next**
4. Switch to the **YAML** tab and paste the contents of [`slack-app-manifest.yaml`](slack-app-manifest.yaml), then click **Next** → **Create**
5. On the app page, go to **OAuth & Permissions** and click **Install to Workspace** → **Allow**
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

The script reads `.env` automatically — no `export` or shell setup needed.

> **Note:** Never commit `.env` to source control — it contains secrets.

### 3. Configure queries

Edit `config/queries.yaml`:

```yaml
jira:
  base_url: https://yourcompany.atlassian.net
  email: you@example.com

slack:
  # bot_token is read from SLACK_BOT_TOKEN env var

queries:
  - name: Open Critical Bugs
    jql: "priority = Critical AND status != Done ORDER BY created DESC"
    channel: "#engineering"
    max_results: 20
    schedule: "09:00"       # optional: daily time for scheduler mode (HH:MM)
    fields:
      - key
      - summary
      - assignee
      - status
      - priority
```

**Available fields:** `key`, `summary`, `assignee`, `status`, `priority`, `issuetype`, `reporter`

---

## Usage

```bash
make list                          # list all configured queries
make run                           # run all queries and post to Slack
make query QUERY="Open CDS CR's"   # run a single query by name
make schedule                      # start the scheduler daemon
```

Or use `python` directly (the venv must be active or use `.venv/bin/python`):

```bash
python main.py run --query "Open CDS CR's"
python main.py --config /path/to/other.yaml run
```

### Running on a schedule with cron

Instead of the built-in scheduler, you can use cron to run on a schedule:

```bash
# crontab -e
0 9 * * 1-5 cd /path/to/jql-to-slack-notifier && python main.py run
```

---

## Testing

```bash
make test
```

Tests cover all four modules and make no real network calls — Jira and Slack APIs are fully mocked.

| File | What's tested |
|------|--------------|
| `tests/test_formatter.py` | Emoji mapping, Block Kit structure, chunking, truncation |
| `tests/test_jira_client.py` | API URL, auth, field normalization, error handling |
| `tests/test_slack_client.py` | Payload shape, auth header, API error handling |
| `tests/test_runner.py` | Config loading, env var injection, query name matching |

---

## Project structure

```
jql-to-slack-notifier/
├── config/
│   └── queries.yaml           # JQL queries, channels, schedule times
├── src/
│   ├── jira_client.py         # Jira Cloud REST API v3
│   ├── slack_client.py        # Slack Web API (chat.postMessage)
│   ├── formatter.py           # Block Kit message builder
│   └── runner.py              # Orchestration
├── tests/
│   ├── test_formatter.py
│   ├── test_jira_client.py
│   ├── test_slack_client.py
│   └── test_runner.py
├── main.py                    # CLI entrypoint
├── Makefile                   # venv setup and run targets
├── slack-app-manifest.yaml    # Import this to create the Slack app
├── requirements.txt
└── .env.example
```
