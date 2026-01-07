---
tags:
- ai-generated
- git
---

A command-line tool for searching a git repository for lines authored by specific authors.

## Features

- Search for patterns in your git repository
- Filter results by author name or email
- Regular expression support for both patterns and author names
- Case-insensitive searching options
- Shows file names, line numbers, and author information

## Installation

Just put it in your path:

```bash
ln -s $(pwd)/git-blamegrep.py /usr/local/bin/git-blamegrep
```

## Usage

```bash
./git-blamegrep.py PATTERN [paths...] [options]
```

### Arguments

- `PATTERN`: Regular expression pattern to search for (required)
- `paths`: Optional files or directories to search (default: all tracked files)

### Options

- `-a, --author AUTHOR`: Filter by author name (supports regex)
- `-i, --ignore-case`: Case-insensitive pattern matching
- `--no-author-case`: Case-insensitive author matching
- `-n, --line-number`: Show line numbers (default: True)
- `--show-author`: Show author name (default: True)

## Examples

### Find all TODOs written by a specific author

```bash
./git-blamegrep.py "TODO" --author "John Doe"
```

### Search for function definitions by author (case-insensitive)

```bash
./git-blamegrep.py "def \w+" --author "jane" --no-author-case -i
```

### Find all console.log statements by any author with "smith" in their name

```bash
./git-blamegrep.py "console\.log" --author "smith" --no-author-case
```

### Search specific files only

```bash
./git-blamegrep.py "import" src/main.py src/utils.py
```

### Search in a specific directory

```bash
./git-blamegrep.py "class \w+" src/ --author "bob"
```

## Output Format

```
filename.py:42 (Author Name): matching line content
```

## Exit Status

- 0: Matches found
- 1: No matches found or error occurred

## How It Works

The tool uses `git blame --line-porcelain` to get authorship information for each line in tracked files, then filters the results based on:
1. The search pattern (regex) matching the line content
2. The author pattern (if specified) matching the author name
