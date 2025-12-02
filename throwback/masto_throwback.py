"""Append historical Mastodon toots from SQLite database to today's Obsidian note."""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import html
import re
import sqlite3
from pathlib import Path
from typing import List, Tuple


HEADER_LINE = "## Vanhat tuuttaukset"


def subtract_years(source: dt.date, years: int) -> dt.date:
    year = source.year - years
    if year < 1:
        raise ValueError("Resulting year must be at least 1")
    day = source.day
    month = source.month
    day = min(day, calendar.monthrange(year, month)[1])
    return dt.date(year, month, day)


def gather_target_dates(today: dt.date) -> List[Tuple[str, dt.date]]:
    """Generate list of target dates to look for (1 year ago, 2 years ago, etc.)."""
    targets: List[Tuple[str, dt.date]] = []

    # Start from 1 year ago
    years_back = 1
    while True:
        try:
            target_date = subtract_years(today, years_back)
            # Stop if we go before a reasonable cutoff (e.g., 2010)
            if target_date.year < 2010:
                break

            if years_back == 1:
                label = "1 vuosi sitten"
            else:
                label = f"{years_back} vuotta sitten"

            targets.append((label, target_date))
            years_back += 1
        except ValueError:
            break

    return targets


def strip_html_tags(html_content: str) -> str:
    """Remove HTML tags and decode HTML entities."""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', html_content)
    # Decode HTML entities
    text = html.unescape(text)
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def find_historical_toots(
    db_path: Path,
    targets: List[Tuple[str, dt.date]]
) -> List[Tuple[str, str, str, int]]:
    """Query database for toots from historical dates.

    Returns a list of tuples: (label, url, preview_text, thread_count)
    where thread_count is the number of toots in the thread (1 for standalone toots)
    """
    historical = []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for label, target_date in targets:
        # Query for toots on this specific date
        # The created_at field is in ISO format like "2023-02-25T04:37:28.762Z"
        date_pattern = f"{target_date.isoformat()}%"

        cursor.execute(
            """
            SELECT id, url, content, created_at, in_reply_to_id
            FROM statuses
            WHERE created_at LIKE ?
            AND url IS NOT NULL
            ORDER BY created_at
            """,
            (date_pattern,)
        )

        toots = cursor.fetchall()

        # Build a map of toot_id -> toot data
        toot_map = {}
        for toot_id, url, content, created_at, in_reply_to_id in toots:
            toot_map[toot_id] = {
                'url': url,
                'content': content,
                'created_at': created_at,
                'in_reply_to_id': in_reply_to_id,
                'is_thread_start': in_reply_to_id is None or in_reply_to_id not in toot_map
            }

        # For each thread starter, count how many toots are in the thread
        for toot_id, toot_data in toot_map.items():
            if not toot_data['is_thread_start']:
                continue  # Skip replies, only process thread starters

            # Count toots in this thread
            thread_count = 1
            for other_id, other_data in toot_map.items():
                if other_id == toot_id:
                    continue
                # Check if this toot is part of the thread (replies to any toot in thread)
                current_reply_to = other_data['in_reply_to_id']
                while current_reply_to:
                    if current_reply_to == toot_id:
                        thread_count += 1
                        break
                    # Check if replying to another toot in our thread
                    if current_reply_to in toot_map:
                        current_reply_to = toot_map[current_reply_to]['in_reply_to_id']
                    else:
                        break

            # Strip HTML tags and get preview text
            preview = strip_html_tags(toot_data['content']) if toot_data['content'] else ""

            if preview:
                historical.append((label, toot_data['url'], preview, thread_count))

    conn.close()
    return historical


def append_toots(
    today_note: Path,
    historical_toots: List[Tuple[str, str, str, int]],
    *,
    dry_run: bool = False,
) -> int:
    """Append historical toots to today's note."""
    existing_content = today_note.read_text(encoding="utf-8") if today_note.exists() else ""

    new_lines: List[str] = []
    if existing_content and not existing_content.endswith("\n"):
        new_lines.append("")

    # Add toots section header if needed
    if not historical_toots:
        return 0

    if HEADER_LINE not in existing_content:
        new_lines.extend(["", HEADER_LINE, ""])

    toots_appended = 0
    for label, url, preview, thread_count in historical_toots:
        # Truncate preview text if too long
        if len(preview) > 256:
            preview_text = preview[:256] + "..."
        else:
            preview_text = preview

        # Add thread indicator if this is a thread
        if thread_count > 1:
            thread_indicator = f" 🧵 ({thread_count} messages)"
        else:
            thread_indicator = ""

        line = f"- {label}: {preview_text}{thread_indicator} ([mastodon]({url}))"

        # Skip if already in the note
        if line in existing_content or line in new_lines:
            continue

        new_lines.append(line)
        toots_appended += 1

    if not new_lines or toots_appended == 0:
        return 0

    block = "\n".join(new_lines) + "\n"

    if dry_run:
        print(block, end="")
        return toots_appended

    if not existing_content.endswith("\n"):
        existing_content += "\n"

    today_note.write_text(existing_content + block, encoding="utf-8")
    return toots_appended


def resolve_today_note(vault_path: Path, diary_dir: str, target_date: dt.date) -> Path:
    """Get the path to today's note, creating it if needed."""
    diary_path = vault_path / diary_dir
    diary_path.mkdir(parents=True, exist_ok=True)
    today_note = diary_path / f"{target_date.isoformat()}.md"
    if not today_note.exists():
        today_note.write_text("", encoding="utf-8")
    return today_note


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append historical Mastodon toots from SQLite database to today's Obsidian note."
    )
    parser.add_argument(
        "vault",
        type=Path,
        help="Path to the Obsidian vault root directory.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("/Users/miikka/code/miikkas-masto-history/masto.db"),
        help="Path to the SQLite database file (default: /Users/miikka/code/miikkas-masto-history/masto.db).",
    )
    parser.add_argument(
        "--diary-dir",
        default="diary",
        help="Relative path from the vault root to the diary folder (default: diary).",
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

    db_path = args.db.expanduser().resolve()
    if not db_path.exists():
        raise SystemExit(f"Database file does not exist: {db_path}")

    target_date: dt.date = args.date
    diary_dir = args.diary_dir.strip("/")

    today_note = resolve_today_note(vault_path, diary_dir, target_date)
    targets = gather_target_dates(target_date)

    # Query database for historical toots
    historical_toots = find_historical_toots(db_path, targets)

    toots_count = append_toots(today_note, historical_toots, dry_run=args.dry_run)

    if toots_count == 0:
        print("No historical toots found to append.")
    elif args.dry_run:
        print(f"Dry run: would append {toots_count} toot(s).")
    else:
        print(f"Appended {toots_count} toot(s).")


if __name__ == "__main__":
    main()
