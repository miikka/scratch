#!/usr/bin/env python3
"""
Count completed tasks in OmniFocus for the Jacksnipe folder.
Reports counts for the last complete week (Thu-Wed) and current week (since last Thu).
"""

import subprocess
import argparse
from datetime import datetime, date, timedelta


def get_last_thursday(reference_date):
    """Get the most recent Thursday on or before the reference date."""
    days_since_thursday = (reference_date.weekday() - 3) % 7
    return reference_date - timedelta(days=days_since_thursday)


def get_week_ranges(reference_date):
    """
    Calculate the date ranges for the current and last complete weeks.
    Weeks run Thursday to Wednesday.

    Returns:
        tuple: (current_week_start, last_week_start, last_week_end)
    """
    current_week_start = get_last_thursday(reference_date)
    last_week_end = current_week_start - timedelta(days=1)  # Wednesday before
    last_week_start = current_week_start - timedelta(days=7)  # Previous Thursday

    return current_week_start, last_week_start, last_week_end


def get_completed_tasks(folder_name, start_date, end_date=None):
    """
    Get tasks completed in OmniFocus within the given folder and date range.

    Args:
        folder_name: Name of the folder to filter by
        start_date: Start date (inclusive)
        end_date: End date (inclusive), or None for up to now

    Returns:
        List of dicts with 'name' and 'project' keys
    """
    if end_date:
        end_date_applescript = f'''
        set endDate to current date
        set year of endDate to {end_date.year}
        set month of endDate to {end_date.month}
        set day of endDate to {end_date.day}
        set hours of endDate to 23
        set minutes of endDate to 59
        set seconds of endDate to 59
        '''
        end_condition = "and completionDate ≤ endDate"
    else:
        end_date_applescript = ""
        end_condition = ""

    applescript = f'''
    use AppleScript version "2.4"
    use scripting additions

    set startDate to current date
    set year of startDate to {start_date.year}
    set month of startDate to {start_date.month}
    set day of startDate to {start_date.day}
    set hours of startDate to 0
    set minutes of startDate to 0
    set seconds of startDate to 0

    {end_date_applescript}

    tell application "OmniFocus"
        tell default document
            set taskList to {{}}

            -- Find the folder
            set targetFolder to missing value
            repeat with aFolder in folders
                if name of aFolder is "{folder_name}" then
                    set targetFolder to aFolder
                    exit repeat
                end if
            end repeat

            if targetFolder is missing value then
                return "Error: Folder not found"
            end if

            -- Get all completed tasks in projects within this folder
            set folderProjects to every flattened project of targetFolder

            repeat with aProject in folderProjects
                set projectName to name of aProject
                set projectTasks to every flattened task of aProject
                repeat with aTask in projectTasks
                    if completed of aTask is true then
                        set completionDate to completion date of aTask
                        if completionDate is not missing value then
                            if completionDate ≥ startDate {end_condition} then
                                set taskName to name of aTask
                                set end of taskList to {{taskName:taskName, taskProject:projectName}}
                            end if
                        end if
                    end if
                end repeat
            end repeat

            return taskList
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
        output = result.stdout.strip()
        if output.startswith("Error:"):
            print(output)
            return []
        return parse_applescript_output(output)
    except subprocess.CalledProcessError as e:
        print(f"Error querying OmniFocus: {e.stderr}")
        return []


def parse_applescript_output(output):
    """Parse the AppleScript output into a list of tasks."""
    if not output.strip():
        return []

    tasks = []
    # AppleScript returns format like: taskName:Task 1, taskProject:Project 1, taskName:Task 2, ...
    parts = output.split(', ')

    current_task = {}
    for part in parts:
        if 'taskName:' in part:
            if current_task:
                tasks.append(current_task)
            task_name = part.split('taskName:', 1)[1]
            current_task = {'name': task_name, 'project': ''}
        elif 'taskProject:' in part and current_task:
            task_project = part.split('taskProject:', 1)[1]
            current_task['project'] = task_project

    if current_task:
        tasks.append(current_task)

    return tasks


def print_tasks(tasks, header, verbose):
    """Print task count and optionally list tasks."""
    print(f"{header}: {len(tasks)} tasks")
    if verbose:
        for task in tasks:
            print(f"  - {task['name']} ({task['project']})")


def main():
    parser = argparse.ArgumentParser(
        description='Count completed tasks in OmniFocus for the Jacksnipe folder.'
    )
    parser.add_argument(
        '--date',
        type=lambda s: datetime.strptime(s, '%Y-%m-%d').date(),
        default=date.today(),
        help='Reference date (YYYY-MM-DD). Defaults to today.'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='List individual tasks'
    )

    args = parser.parse_args()
    reference_date = args.date

    current_week_start, last_week_start, last_week_end = get_week_ranges(reference_date)

    # Get tasks for each period
    last_week_tasks = get_completed_tasks("Jacksnipe", last_week_start, last_week_end)
    current_week_tasks = get_completed_tasks("Jacksnipe", current_week_start)

    # Format output
    print_tasks(
        last_week_tasks,
        f"Last week ({last_week_start.strftime('%Y-%m-%d')} to {last_week_end.strftime('%Y-%m-%d')})",
        args.verbose
    )
    print_tasks(
        current_week_tasks,
        f"This week (since {current_week_start.strftime('%Y-%m-%d')})",
        args.verbose
    )


if __name__ == "__main__":
    main()
