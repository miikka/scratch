#!/usr/bin/env python3
"""
git-blamegrep: Search for lines in a git repository authored by a specific author.
Combines git blame functionality with grep-like pattern matching.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, List, Tuple


def run_git_command(args: List[str], cwd: Optional[Path] = None) -> str:
    """Run a git command and return its output."""
    try:
        result = subprocess.run(
            ['git'] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running git command: {e.stderr}", file=sys.stderr)
        sys.exit(1)


def get_tracked_files(path: Optional[str] = None, cwd: Optional[Path] = None) -> List[str]:
    """Get list of tracked files in the repository."""
    args = ['ls-files']
    if path:
        args.append(path)

    output = run_git_command(args, cwd)
    return [f for f in output.strip().split('\n') if f]


def git_blame_file(filepath: str, cwd: Optional[Path] = None) -> List[Tuple[str, str, int, str]]:
    """
    Run git blame on a file and return blame information.
    Returns list of tuples: (commit_hash, author, line_number, line_content)
    """
    try:
        # Use porcelain format for easier parsing
        output = run_git_command(['blame', '--line-porcelain', filepath], cwd)
    except:
        return []

    results = []
    lines = output.split('\n')
    i = 0

    while i < len(lines):
        if not lines[i]:
            i += 1
            continue

        # First line: commit hash, original line, final line, num lines
        parts = lines[i].split()
        if not parts:
            i += 1
            continue

        commit_hash = parts[0]

        # Parse metadata
        author = None
        line_content = None
        line_num = None

        i += 1
        while i < len(lines):
            line = lines[i]

            if line.startswith('author '):
                author = line[7:]
            elif line.startswith('author-mail '):
                author_email = line[12:]
            elif line.startswith('\t'):
                # This is the actual line content
                line_content = line[1:]  # Remove the tab
                # Line number is from the first line parts
                if len(parts) >= 3:
                    line_num = int(parts[2])
                i += 1
                break

            i += 1

        if author and line_content is not None and line_num is not None:
            results.append((commit_hash, author, line_num, line_content))

    return results


def search_in_file(
    filepath: str,
    pattern: re.Pattern,
    author_pattern: Optional[re.Pattern],
    case_insensitive: bool,
    cwd: Optional[Path] = None
) -> List[Tuple[str, int, str, str]]:
    """
    Search for pattern in file and filter by author.
    Returns list of tuples: (filepath, line_number, author, line_content)
    """
    blame_info = git_blame_file(filepath, cwd)
    results = []

    for commit_hash, author, line_num, line_content in blame_info:
        # Check if line matches the search pattern
        if pattern.search(line_content):
            # Check if author matches (if author filter is specified)
            if author_pattern is None or author_pattern.search(author):
                results.append((filepath, line_num, author, line_content))

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Search for lines in a git repository authored by a specific author.',
        epilog='Example: git-blamegrep.py "TODO" --author "John Doe"'
    )

    parser.add_argument(
        'pattern',
        help='Regular expression pattern to search for'
    )

    parser.add_argument(
        'paths',
        nargs='*',
        help='Files or directories to search (default: all tracked files)'
    )

    parser.add_argument(
        '-a', '--author',
        help='Filter by author name (supports regex)'
    )

    parser.add_argument(
        '-i', '--ignore-case',
        action='store_true',
        help='Case-insensitive pattern matching'
    )

    parser.add_argument(
        '--no-author-case',
        action='store_true',
        help='Case-insensitive author matching'
    )

    parser.add_argument(
        '-n', '--line-number',
        action='store_true',
        default=True,
        help='Show line numbers (default: True)'
    )

    parser.add_argument(
        '--show-author',
        action='store_true',
        default=True,
        help='Show author name (default: True)'
    )

    parser.add_argument(
        '-C', '--context',
        type=int,
        metavar='NUM',
        help='Show NUM lines of context around matches'
    )

    args = parser.parse_args()

    # Compile search pattern
    flags = re.IGNORECASE if args.ignore_case else 0
    try:
        pattern = re.compile(args.pattern, flags)
    except re.error as e:
        print(f"Invalid regex pattern: {e}", file=sys.stderr)
        sys.exit(1)

    # Compile author pattern if specified
    author_pattern = None
    if args.author:
        author_flags = re.IGNORECASE if args.no_author_case else 0
        try:
            author_pattern = re.compile(args.author, author_flags)
        except re.error as e:
            print(f"Invalid author regex pattern: {e}", file=sys.stderr)
            sys.exit(1)

    # Get list of files to search
    cwd = Path.cwd()

    if args.paths:
        files = []
        for path in args.paths:
            path_obj = Path(path)
            if path_obj.is_file():
                files.append(path)
            elif path_obj.is_dir():
                files.extend(get_tracked_files(path, cwd))
            else:
                print(f"Warning: {path} not found", file=sys.stderr)
    else:
        files = get_tracked_files(cwd=cwd)

    # Search each file
    total_matches = 0
    for filepath in files:
        matches = search_in_file(filepath, pattern, author_pattern, args.ignore_case, cwd)

        for file, line_num, author, line_content in matches:
            total_matches += 1

            # Format output
            parts = [file]
            if args.line_number:
                parts.append(f":{line_num}")
            if args.show_author:
                parts.append(f" ({author})")
            parts.append(f": {line_content}")

            print(''.join(parts))

    return 0 if total_matches > 0 else 1


if __name__ == '__main__':
    sys.exit(main())
