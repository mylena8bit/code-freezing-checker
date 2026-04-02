import argparse
import datetime
import logging
import os
import sys
from dataclasses import dataclass
from typing import Optional

import yaml

DEFAULT_CONFIG_FILE = "config/config.yml"

logging.basicConfig(
    format="[%(asctime)s] [%(levelname)s] - %(message)s",
    # UTC
    datefmt="%m-%d-%Y %I:%M:%S",
    level=logging.INFO,
)


@dataclass(frozen=True)
class FreezePeriod:
    name: str
    date_from: datetime.date
    date_to: datetime.date

    def contains(self, reference_date: datetime.date) -> bool:
        return self.date_from <= reference_date <= self.date_to

    def days_until_start(self, reference_date: datetime.date) -> int:
        return (self.date_from - reference_date).days


def get_config(filename: str) -> dict:
    try:
        with open(filename, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logging.error("Config file '%s' was not found", filename)
        sys.exit(1)
    except yaml.YAMLError as exc:
        logging.error("Config file '%s' has invalid YAML: %s", filename, exc)
        sys.exit(1)


def unpack_config(config: dict) -> tuple:
    try:
        bypass_group = config["bypass_group"]
        freezing_dates = config["freezing_dates"]
    except KeyError:
        logging.error(
            "One of the required fields is missing: 'bypass_group' or 'freezing_dates'"
        )
        sys.exit(1)
    if not isinstance(bypass_group, list):
        logging.error("Field 'bypass_group' must be a list")
        sys.exit(1)
    if not isinstance(freezing_dates, dict):
        logging.error("Field 'freezing_dates' must be a map/object")
        sys.exit(1)
    return (bypass_group, freezing_dates)


def is_user_in_bypass_group(username: str, bypass_group: list) -> bool:
    if not username:
        return False
    return username in bypass_group


def is_today_within_freezing_date(date_from: datetime.date, date_to: datetime.date) -> bool:
    date_today = datetime.date.today()
    return date_from <= date_today <= date_to


def parse_date(value, period_name: str, field_name: str) -> datetime.date:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value)
        except ValueError:
            logging.error(
                "Invalid date in period '%s' field '%s'. Expected ISO date (YYYY-MM-DD), got '%s'",
                period_name,
                field_name,
                value,
            )
            sys.exit(1)

    logging.error(
        "Invalid type for period '%s' field '%s'. Expected date or string, got '%s'",
        period_name,
        field_name,
        type(value).__name__,
    )
    sys.exit(1)


def parse_periods(freezing_dates: dict) -> list[FreezePeriod]:
    periods = []
    for period_name, period_data in freezing_dates.items():
        if not isinstance(period_data, dict):
            logging.error("Period '%s' must be an object with 'from' and 'to'", period_name)
            sys.exit(1)

        date_from = parse_date(period_data.get("from"), period_name, "from")
        date_to = parse_date(period_data.get("to"), period_name, "to")

        if date_from > date_to:
            logging.error(
                "Period '%s' is invalid: 'from' date (%s) cannot be after 'to' date (%s)",
                period_name,
                date_from,
                date_to,
            )
            sys.exit(1)

        periods.append(FreezePeriod(name=period_name, date_from=date_from, date_to=date_to))

    return sorted(periods, key=lambda p: p.date_from)


def get_ci_user(cli_user: Optional[str]) -> Optional[str]:
    if cli_user:
        return cli_user

    return os.getenv("GITHUB_ACTOR")


def resolve_reference_date(cli_date: Optional[str]) -> datetime.date:
    if not cli_date:
        return datetime.date.today()

    try:
        return datetime.date.fromisoformat(cli_date)
    except ValueError:
        logging.error("Invalid --date value '%s'. Expected ISO date (YYYY-MM-DD)", cli_date)
        sys.exit(1)


def find_next_period(periods: list[FreezePeriod], reference_date: datetime.date) -> Optional[FreezePeriod]:
    for period in periods:
        if period.date_from >= reference_date:
            return period
    return None


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Code freezing checker")
    parser.add_argument("--config", default=DEFAULT_CONFIG_FILE, help="Path to config YAML")
    parser.add_argument("--user", default=None, help="CI user/login to evaluate bypass")
    parser.add_argument(
        "--date",
        default=None,
        help="Reference date in ISO format (YYYY-MM-DD). Useful for tests.",
    )
    return parser.parse_args()


def main():
    args = get_args()
    config = get_config(args.config)
    bypass_group, freezing_dates = unpack_config(config)
    periods = parse_periods(freezing_dates)
    ci_user = get_ci_user(args.user)
    today = resolve_reference_date(args.date)

    logging.info("Checking freeze windows for date %s", today)

    if ci_user and is_user_in_bypass_group(ci_user, bypass_group):
        logging.info("User '%s' is in bypass group, exiting", ci_user)
        sys.exit(0)

    if not ci_user:
        logging.warning("No CI user was found in environment variable GITHUB_ACTOR.")

    for period in periods:
        logging.info(
            "Validating period '%s' from %s to %s",
            period.name,
            period.date_from,
            period.date_to,
        )
        if period.contains(today):
            logging.warning(
                "The date %s falls under '%s'. Merge/deploy blocked due to code freezing period.",
                today,
                period.name,
            )
            sys.exit(1)

    next_period = find_next_period(periods, today)
    if next_period:
        logging.info(
            "No active freeze. Next freeze is '%s' starting in %s day(s) on %s.",
            next_period.name,
            next_period.days_until_start(today),
            next_period.date_from,
        )
    else:
        logging.info("No active freeze and no upcoming freeze windows configured.")

    sys.exit(0)


if __name__ == '__main__':
    main()
