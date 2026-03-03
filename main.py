#!/usr/bin/env python3
"""
JQL -> Slack notification tool.

Commands:
  run                     Run all configured queries once
  run --query NAME        Run a single query by name
  list                    List all configured queries
  schedule                Start the scheduler daemon (runs queries at their configured times)

Schedule field uses standard 5-field cron syntax:
  "0 8 * * 1-5"   ->  08:00 Monday-Friday
  "30 9 * * *"    ->  09:30 every day
  "0 8,17 * * *"  ->  08:00 and 17:00 every day
Timezone is taken from the top-level `timezone:` key in config (default: UTC).
"""

import argparse
import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.runner import load_config, run_all, run_named


def cmd_run(args) -> None:
    config = load_config(args.config)
    if args.query:
        run_named(config, args.query)
    else:
        run_all(config)


def cmd_list(args) -> None:
    config = load_config(args.config)
    queries = config.get("queries", [])
    if not queries:
        print("No queries configured.")
        return
    print(f"{'Name':<35} {'Channel':<20} {'Schedule':<10} {'Max'}")
    print("-" * 75)
    for q in queries:
        print(
            f"{q['name']:<35} "
            f"{q.get('channel', ''):<20} "
            f"{q.get('schedule', '-'):<10} "
            f"{q.get('max_results', 50)}"
        )


def cmd_schedule(args) -> None:
    config = load_config(args.config)
    global_tz = config.get("timezone", "UTC")
    queries = config.get("queries", [])

    scheduler = BlockingScheduler(timezone=global_tz)

    for q in queries:
        cron_expr = q.get("schedule")
        if not cron_expr:
            continue

        job_tz = q.get("timezone", global_tz)

        def make_job(query_cfg):
            def job():
                from src.runner import _make_clients, run_query
                jira, slack = _make_clients(config)
                base_url = config["jira"]["base_url"]
                emoji_config = config.get("emojis")
                tz = config.get("timezone", "UTC")
                try:
                    run_query(query_cfg, jira, slack, base_url, emoji_config, tz)
                except Exception as e:
                    print(f"[ERROR] {query_cfg['name']}: {e}", file=sys.stderr)
            return job

        trigger = CronTrigger.from_crontab(cron_expr, timezone=job_tz)
        scheduler.add_job(make_job(q), trigger, name=q["name"])
        print(f"Scheduled: {q['name']} -- {cron_expr} ({job_tz})")

    if not scheduler.get_jobs():
        print("No queries have a 'schedule' field set. Nothing to schedule.")
        sys.exit(1)

    print(f"\nScheduler running ({len(scheduler.get_jobs())} job(s)). Press Ctrl+C to stop.\n")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\nScheduler stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run JQL searches and post results to Slack.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--config",
        default="config/queries.yaml",
        metavar="PATH",
        help="Path to config file (default: config/queries.yaml)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging (shows Jira HTTP requests)",
    )
    subparsers = parser.add_subparsers(dest="command")

    # run
    run_parser = subparsers.add_parser("run", help="Run queries and post to Slack")
    run_parser.add_argument(
        "--query",
        metavar="NAME",
        help="Name of a specific query to run (runs all if omitted)",
    )

    # list
    subparsers.add_parser("list", help="List all configured queries")

    # schedule
    subparsers.add_parser("schedule", help="Start the scheduler daemon")

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
        )

    if args.command == "run":
        cmd_run(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "schedule":
        cmd_schedule(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
