#!/usr/bin/env python3
"""
Get tasks completed today from OmniFocus and update a Markdown file.
"""

import subprocess
import json
import argparse
import re
from datetime import datetime, date
from pathlib import Path


HEADER = "## Tänään tehty"


def get_completed_tasks_today():
    """Query OmniFocus for tasks completed today using AppleScript."""

    # AppleScript to get tasks completed today
    applescript = '''
    use AppleScript version "2.4"
    use scripting additions
    use framework "Foundation"

    set today to current date
    set hours of today to 0
    set minutes of today to 0
    set seconds of today to 0

    tell application "OmniFocus"
        tell default document
            set completedTasks to {}
            set allTasks to flattened tasks

            repeat with aTask in allTasks
                if completed of aTask is true then
                    set completionDate to completion date of aTask
                    if completionDate is not missing value then
                        if completionDate ≥ today then
                            set taskName to name of aTask
                            set taskNote to note of aTask
                            set taskProject to ""
                            if containing project of aTask is not missing value then
                                set taskProject to name of containing project of aTask
                            end if
                            set end of completedTasks to {taskName:taskName, taskNote:taskNote, taskProject:taskProject}
                        end if
                    end if
                end if
            end repeat

            return completedTasks
        end tell
    end tell
    '''

    try:
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            check=True
        )
        return parse_applescript_output(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error querying OmniFocus: {e.stderr}")
        return []


def parse_applescript_output(output):
    """Parse the AppleScript output into a list of tasks."""
    if not output.strip():
        return []

    tasks = []
    # AppleScript returns a list format like: taskName:Task 1, taskNote:Note 1, taskProject:Project 1, taskName:Task 2, taskNote:Note 2, taskProject:Project 2
    # We need to parse this format
    lines = output.strip().split(', ')

    current_task = {}
    for line in lines:
        if 'taskName:' in line:
            if current_task:
                tasks.append(current_task)
            task_name = line.split('taskName:', 1)[1]
            current_task = {'name': task_name, 'note': '', 'project': ''}
        elif 'taskNote:' in line and current_task:
            task_note = line.split('taskNote:', 1)[1]
            current_task['note'] = task_note
        elif 'taskProject:' in line and current_task:
            task_project = line.split('taskProject:', 1)[1]
            current_task['project'] = task_project

    if current_task:
        tasks.append(current_task)

    return tasks


def generate_markdown_content(tasks, today_str):
    """Generate Markdown content for tasks."""
    lines = [f"{HEADER} ({today_str})\n"]

    if not tasks:
        lines.append("Tänään ei ole tullut mitään valmiiksi.")
    else:
        for task in tasks:
            task_line = f"- {task['name']}"
            if task.get('project') and task['project'] != 'missing value':
                task_line += f" ({task['project']})"
            lines.append(task_line)
            if task['note'] and task['note'] != 'missing value':
                # Indent notes as a sub-item
                note_lines = task['note'].split('\n')
                for note_line in note_lines:
                    if note_line.strip():
                        lines.append(f"  - {note_line.strip()}")

    return '\n'.join(lines)


def resolve_file_path(path):
    """
    Resolve the file path. If path is a directory (Obsidian vault),
    find today's daily note in the diary subdirectory.
    Returns (file_path, is_vault_mode) tuple.
    """
    path = Path(path)

    if path.is_dir():
        # Treat as Obsidian vault - find today's daily note
        today_str = date.today().strftime("%Y-%m-%d")
        daily_note = path / "diary" / f"{today_str}.md"
        return (daily_note, True)
    else:
        # Regular file path
        return (path, False)


def update_markdown_file(file_path, tasks, is_vault_mode=False):
    """Update the Markdown file with today's tasks, replacing existing section if present."""
    today_str = date.today().strftime("%Y-%m-%d")
    new_content = generate_markdown_content(tasks, today_str)

    file_path = Path(file_path)

    # In vault mode, don't create the file if it doesn't exist
    if not file_path.exists():
        if is_vault_mode:
            print(f"Daily note {file_path} does not exist. Skipping update.")
            return
        else:
            # Create new file
            updated_content = new_content + '\n'
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            print(f"Created {file_path} with {len(tasks)} completed task(s) for {today_str}")
            return

    # Read existing content
    with open(file_path, 'r', encoding='utf-8') as f:
        existing_content = f.read()

    # Look for existing section for today
    pattern = rf'{HEADER} \({re.escape(today_str)}\).*?(?=\n# |\Z)'
    match = re.search(pattern, existing_content, re.DOTALL)

    if match:
        # Replace existing section
        updated_content = existing_content[:match.start()] + new_content + existing_content[match.end():]
        # Clean up any extra blank lines
        updated_content = re.sub(r'\n{3,}', '\n\n', updated_content)
    else:
        # Append new section
        if existing_content and not existing_content.endswith('\n\n'):
            separator = '\n\n' if existing_content.endswith('\n') else '\n\n\n'
        else:
            separator = ''
        updated_content = existing_content + separator + new_content + '\n'

    # Write updated content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)

    print(f"Updated {file_path} with {len(tasks)} completed task(s) for {today_str}")


def main():
    parser = argparse.ArgumentParser(
        description='Get tasks completed today from OmniFocus and update a Markdown file.'
    )
    parser.add_argument(
        'file',
        help='Path to the Markdown file or Obsidian vault directory to update'
    )
    parser.add_argument(
        '--print',
        action='store_true',
        help='Print to stdout instead of updating file'
    )

    args = parser.parse_args()

    tasks = get_completed_tasks_today()

    if args.print:
        # Print mode for backward compatibility
        today_str = date.today().strftime("%Y-%m-%d")
        print(generate_markdown_content(tasks, today_str))
    else:
        # Update file mode
        file_path, is_vault_mode = resolve_file_path(args.file)
        update_markdown_file(file_path, tasks, is_vault_mode)


if __name__ == "__main__":
    main()
