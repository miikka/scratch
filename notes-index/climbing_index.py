#!/usr/bin/env python3

import os
import re
from datetime import datetime
from pathlib import Path

def extract_date_from_filename(filename):
    """Extract date from filename pattern 'Name YYYY-MM-DD.md'"""
    # Match pattern like "Rollarit 2025-04-14.md" or "Kiikkukallio 2025-05-16.md"
    pattern = r'(\d{4}-\d{2}-\d{2})'
    match = re.search(pattern, filename)
    if match:
        try:
            return datetime.strptime(match.group(1), '%Y-%m-%d')
        except ValueError:
            return None
    return None

def get_location_from_path(filepath):
    """Extract location name from the parent directory"""
    return filepath.parent.name

def scan_notes_directory(root_path='.'):
    """Scan directory for markdown notes and return sorted list"""
    notes = []
    root = Path(root_path)
    
    # Find all .md files recursively
    for md_file in root.rglob('*.md'):
        date = extract_date_from_filename(md_file.name)
        if date:  # Only include files with valid dates
            location = get_location_from_path(md_file)
            notes.append({
                'filename': md_file.name,
                'location': location,
                'date': date,
                'path': str(md_file)
            })
    
    # Sort by date, most recent first
    notes.sort(key=lambda x: x['date'], reverse=True)
    return notes

def print_notes_index(notes):
    """Print formatted index of notes in Obsidian-compatible format"""
    if not notes:
        print("No notes found with valid date patterns.")
        return
    
    # Obsidian table header
    print("| Päivämäärä | Sijainti | Tiedosto |")
    print("|------------|----------|----------|")
    
    for note in notes:
        date_str = note['date'].strftime('%Y-%m-%d')
        # Create Obsidian-style link with directory path
        file_without_ext = note['filename'][:-3]  # Remove .md extension
        obsidian_link = f"[[{note['location']}/{file_without_ext}]]"
        print(f"| {date_str} | {note['location']} | {obsidian_link} |")
    
    print(f"\n**Yhteensä:** {len(notes)} kiipeilysessiota")

def main():
    """Main function to generate and display notes index"""
    # You can change this path to point to your notes directory
    notes_directory = "."
    
    try:
        notes = scan_notes_directory(notes_directory)
        print_notes_index(notes)
        
        # Optionally, you can also return the data for further processing
        return notes
        
    except FileNotFoundError:
        print(f"Error: Directory '{notes_directory}' not found.")
    except Exception as e:
        print(f"Error scanning notes: {e}")

if __name__ == "__main__":
    main()
