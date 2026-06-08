"""Append historical quanttype.net blog posts to today's Obsidian note."""

from __future__ import annotations

import argparse
import datetime as dt
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import List, Tuple


HEADER_LINE = "## Vanhat blogipostaukset"
FEED_URL = "https://quanttype.net/index.xml"


def fetch_feed(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "blog-throwback"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def parse_feed(feed_bytes: bytes) -> List[Tuple[str, str, dt.date]]:
    """Parse RSS feed into a list of (title, link, published_date) tuples."""
    root = ET.fromstring(feed_bytes)
    items = []
    for item in root.iterfind("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date_text = (item.findtext("pubDate") or "").strip()
        if not (title and link and pub_date_text):
            continue
        pub_dt = parsedate_to_datetime(pub_date_text)
        items.append((title, link, pub_dt.date()))
    return items


def find_throwbacks(
    items: List[Tuple[str, str, dt.date]],
    today: dt.date,
) -> List[Tuple[str, str, str, dt.date]]:
    """Return (label, title, link, published_date) for posts from this day in prior years."""
    matches = []
    for title, link, published in items:
        if published.month != today.month or published.day != today.day:
            continue
        if published.year >= today.year:
            continue
        years_back = today.year - published.year
        if years_back == 1:
            label = "1 vuosi sitten"
        else:
            label = f"{years_back} vuotta sitten"
        matches.append((label, title, link, published))
    matches.sort(key=lambda m: m[3], reverse=True)
    return matches


def append_posts(
    today_note: Path,
    posts: List[Tuple[str, str, str, dt.date]],
    *,
    dry_run: bool = False,
) -> int:
    existing_content = today_note.read_text(encoding="utf-8") if today_note.exists() else ""

    if not posts:
        return 0

    new_lines: List[str] = []
    if existing_content and not existing_content.endswith("\n"):
        new_lines.append("")

    if HEADER_LINE not in existing_content:
        new_lines.extend(["", HEADER_LINE, ""])

    appended = 0
    for label, title, link, _ in posts:
        line = f"- {label}: [{title}]({link})"
        if line in existing_content or line in new_lines:
            continue
        new_lines.append(line)
        appended += 1

    if appended == 0:
        return 0

    block = "\n".join(new_lines) + "\n"

    if dry_run:
        print(block, end="")
        return appended

    if not existing_content.endswith("\n"):
        existing_content += "\n"

    today_note.write_text(existing_content + block, encoding="utf-8")
    return appended


def resolve_today_note(vault_path: Path, diary_dir: str, target_date: dt.date) -> Path:
    diary_path = vault_path / diary_dir
    diary_path.mkdir(parents=True, exist_ok=True)
    today_note = diary_path / f"{target_date.isoformat()}.md"
    if not today_note.exists():
        today_note.write_text("", encoding="utf-8")
    return today_note


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append quanttype.net blog posts from this day N years ago to today's Obsidian note."
    )
    parser.add_argument(
        "vault",
        type=Path,
        help="Path to the Obsidian vault root directory.",
    )
    parser.add_argument(
        "--feed-url",
        default=FEED_URL,
        help=f"RSS feed URL (default: {FEED_URL}).",
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

    target_date: dt.date = args.date
    diary_dir = args.diary_dir.strip("/")

    today_note = resolve_today_note(vault_path, diary_dir, target_date)

    feed_bytes = fetch_feed(args.feed_url)
    items = parse_feed(feed_bytes)
    posts = find_throwbacks(items, target_date)

    appended = append_posts(today_note, posts, dry_run=args.dry_run)

    if appended == 0:
        print("No historical blog posts found to append.")
    elif args.dry_run:
        print(f"Dry run: would append {appended} blog post(s).")
    else:
        print(f"Appended {appended} blog post(s).")


if __name__ == "__main__":
    main()
