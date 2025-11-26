"""Append links to historical Obsidian diary entries in today's note."""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import re
from pathlib import Path
from typing import List, Tuple


HEADER_LINE = "## Aikakapseli"
TOOTS_HEADER_LINE = "## Vanhat tuuttaukset"


def subtract_months(source: dt.date, months: int) -> dt.date:
    year = source.year
    month = source.month - months
    while month <= 0:
        month += 12
        year -= 1
    day = min(source.day, calendar.monthrange(year, month)[1])
    return dt.date(year, month, day)


def subtract_years(source: dt.date, years: int) -> dt.date:
    year = source.year - years
    if year < 1:
        raise ValueError("Resulting year must be at least 1")
    day = source.day
    month = source.month
    day = min(day, calendar.monthrange(year, month)[1])
    return dt.date(year, month, day)


def formatted_link(diary_dir: str, target_date: dt.date, archive_file: str | None = None) -> str:
    """Create an Obsidian link to a diary entry.

    If archive_file is provided, creates a link to a heading within that file.
    Otherwise, creates a link to an individual diary file.
    """
    if archive_file:
        return f"[[{archive_file}#{target_date.isoformat()}]]"
    return f"[[{diary_dir}/{target_date.isoformat()}]]"


def check_archive_file(vault_path: Path, target_date: dt.date) -> str | None:
    """Check if a date exists in an archive file.

    Returns the relative path to the archive file (e.g., 'archive/Notes 2022')
    if the file exists and contains a heading for the target date, otherwise None.
    """
    year = target_date.year
    archive_file = vault_path / "archive" / f"Notes {year}.md"

    if not archive_file.exists():
        return None

    content = archive_file.read_text(encoding="utf-8")
    heading = f"## {target_date.isoformat()}"

    if heading in content:
        return f"archive/Notes {year}"

    return None


def parse_toots(vault_path: Path) -> List[Tuple[dt.date, str, str]]:
    """Parse Toots.md and extract toots with their dates and URLs.

    Returns a list of tuples: (date, url, preview_text)
    """
    toots_file = vault_path / "Toots.md"
    if not toots_file.exists():
        return []

    content = toots_file.read_text(encoding="utf-8")
    toots = []

    # Pattern: [2023-02-25T04:37:28.762Z](URL): <p>content</p>
    pattern = r'\[(\d{4}-\d{2}-\d{2})T[^\]]+\]\(([^)]+)\):\s*(?:<p>)?([^<\n]+)'

    for match in re.finditer(pattern, content):
        date_str = match.group(1)
        url = match.group(2)
        preview = match.group(3).strip()

        try:
            toot_date = dt.date.fromisoformat(date_str)
            toots.append((toot_date, url, preview))
        except ValueError:
            continue

    return toots


def find_historical_toots(
    toots: List[Tuple[dt.date, str, str]],
    targets: List[Tuple[str, dt.date]],
    today: dt.date
) -> List[Tuple[str, str, str]]:
    """Find toots from historical dates.

    Returns a list of tuples: (label, url, preview_text)
    """
    historical = []

    for label, target_date in targets:
        # Only include toots for dates 1+ year ago
        days_ago = (today - target_date).days
        if days_ago < 365:
            continue

        for toot_date, url, preview in toots:
            if toot_date == target_date:
                historical.append((label, url, preview))

    return historical


def gather_targets(today: dt.date) -> List[Tuple[str, dt.date]]:
    targets: List[Tuple[str, dt.date]] = []

    targets.append(("1 kuukausi sitten", subtract_months(today, 1)))
    targets.append(("3 kuukautta sitten", subtract_months(today, 3)))
    targets.append(("1 vuosi sitten", subtract_years(today, 1)))

    years_back = 2
    while today.year - years_back >= 2021:
        targets.append((f"{years_back} vuotta sitten", subtract_years(today, years_back)))
        years_back += 1

    return targets


def append_links(
    today_note: Path,
    vault_path: Path,
    diary_dir: str,
    targets: List[Tuple[str, dt.date]],
    historical_toots: List[Tuple[str, str, str]],
    *,
    dry_run: bool = False,
) -> Tuple[int, int]:
    diary_root = today_note.parent
    existing_content = today_note.read_text(encoding="utf-8") if today_note.exists() else ""

    new_lines: List[str] = []
    if existing_content and not existing_content.endswith("\n"):
        new_lines.append("")

    # Add diary entries section
    if HEADER_LINE not in existing_content:
        new_lines.extend(["", HEADER_LINE, ""])

    diary_appended = 0
    for label, target_date in targets:
        # First check if individual diary note exists
        target_path = diary_root / f"{target_date.isoformat()}.md"
        archive_file = None

        if target_path.exists():
            # Individual diary note exists
            link = formatted_link(diary_dir, target_date)
        else:
            # Check if date exists in an archive file
            archive_file = check_archive_file(vault_path, target_date)
            if not archive_file:
                continue
            link = formatted_link(diary_dir, target_date, archive_file)

        line = f"- {label}: {link}"
        if line in existing_content or line in new_lines:
            continue

        new_lines.append(line)
        diary_appended += 1

    # Add toots section
    toots_appended = 0
    if historical_toots:
        if TOOTS_HEADER_LINE not in existing_content:
            new_lines.extend(["", TOOTS_HEADER_LINE, ""])

        for label, url, preview in historical_toots:
            # Show preview text and Mastodon link
            line = f"- {label}: {preview[:256]}... ([mastodon]({url}))"
            if line in existing_content or line in new_lines:
                continue

            new_lines.append(line)
            toots_appended += 1

    if not new_lines or (diary_appended == 0 and toots_appended == 0):
        return (0, 0)

    block = "\n".join(new_lines) + "\n"

    if dry_run:
        print(block, end="")
        return (diary_appended, toots_appended)

    if not existing_content.endswith("\n"):
        existing_content += "\n"

    today_note.write_text(existing_content + block, encoding="utf-8")
    return (diary_appended, toots_appended)


def resolve_today_note(vault_path: Path, diary_dir: str, target_date: dt.date) -> Path:
    diary_path = vault_path / diary_dir
    diary_path.mkdir(parents=True, exist_ok=True)
    today_note = diary_path / f"{target_date.isoformat()}.md"
    if not today_note.exists():
        today_note.write_text("", encoding="utf-8")
    return today_note


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append historical diary links to today's Obsidian note."
    )
    parser.add_argument(
        "vault",
        type=Path,
        help="Path to the Obsidian vault root directory.",
    )
    parser.add_argument(
        "--diary-dir",
        default="diary",
        help="Relative path from the vault root to the diary folder.",
    )
    parser.add_argument(
        "--date",
        type=lambda s: dt.date.fromisoformat(s),
        default=dt.date.today(),
        help="Override today's date (ISO format YYYY-MM-DD).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the Markdown that would be appended without modifying the file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    vault_path = args.vault.expanduser().resolve()
    if not vault_path.exists():
        raise SystemExit(f"Vault path does not exist: {vault_path}")

    target_date: dt.date = args.date
    diary_dir = args.diary_dir.strip("/")

    today_note = resolve_today_note(vault_path, diary_dir, target_date)
    targets = gather_targets(target_date)

    # Parse toots and find historical ones
    toots = parse_toots(vault_path)
    historical_toots = find_historical_toots(toots, targets, target_date)

    diary_count, toots_count = append_links(
        today_note, vault_path, diary_dir, targets, historical_toots, dry_run=args.dry_run
    )

    total_count = diary_count + toots_count

    if total_count == 0:
        print("No historical entries found to append.")
    elif args.dry_run:
        parts = []
        if diary_count > 0:
            parts.append(f"{diary_count} diary link(s)")
        if toots_count > 0:
            parts.append(f"{toots_count} toot(s)")
        print(f"Dry run: would append {' and '.join(parts)}.")
    else:
        parts = []
        if diary_count > 0:
            parts.append(f"{diary_count} diary link(s)")
        if toots_count > 0:
            parts.append(f"{toots_count} toot(s)")
        print(f"Appended {' and '.join(parts)}.")


if __name__ == "__main__":
    main()
