#!/usr/bin/env python3
"""
Translation Verification Tool
Reads a JSON file with French translations of English glosses for Chinese characters.
Allows user to verify translations as good/bad/unsure and organizes results in subdirectories.
Supports resuming from last session and undo functionality.
"""

import json
import os
import sys
import tty
import termios
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime


class TranslationChecker:

    def __init__(self, json_file: str = "gloss_translation-qwen-max.json"):
        """Initialize the translation checker."""
        self.json_file = json_file
        self.base_dir = Path(__file__).parent
        self.output_dir = self.base_dir / "translation_review"
        self.state_file = self.output_dir / "state.json"

        # Create output directories
        self.output_dir.mkdir(exist_ok=True)

        # Load data
        self.translations = self._load_json(self.json_file)
        self.state = self._load_state()
        self.history: List[Tuple[str, str]] = []  # Track actions for undo

    def _load_json(self, filepath: str) -> Dict:
        """Load JSON file."""
        path = self.base_dir / filepath
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: File not found: {path}")
            exit(1)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in {path}")
            exit(1)

    def _load_state(self) -> Dict:
        """Load state from previous session."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {"good": [], "bad": [], "unsure": []}
        return {"good": [], "bad": [], "unsure": []}

    def _save_state(self):
        """Save current state."""
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def _sync_all_category_files(self):
        """Update all three category files based on current state."""
        for category in ["good", "bad", "unsure"]:
            category_file = self.output_dir / f"{category}_translations.json"

            # Build entries for this category
            entries = {}
            for char in self.state.get(category, []):
                if char in self.translations:
                    entries[char] = {"char": char, "gloss_en": self.translations[char].get("gloss_en", ""), "gloss_fr": self.translations[char].get("gloss_fr", "")}

            # Save
            with open(category_file, 'w', encoding='utf-8') as f:
                json.dump(entries, f, ensure_ascii=False, indent=2)

    def _save_entry(self, char: str, category: str):
        """Save entry to appropriate category file."""
        if char not in self.translations:
            return

        entry = {"char": char, "gloss_en": self.translations[char].get("gloss_en", ""), "gloss_fr": self.translations[char].get("gloss_fr", "")}

        category_file = self.output_dir / f"{category}_translations.json"

        # Load existing entries
        entries = {}
        if category_file.exists():
            try:
                with open(category_file, 'r', encoding='utf-8') as f:
                    entries = json.load(f)
            except json.JSONDecodeError:
                entries = {}

        # Add/update entry
        entries[char] = entry

        # Save
        with open(category_file, 'w', encoding='utf-8') as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)

    def _remove_entry(self, char: str, category: str):
        """Remove entry from category file."""
        category_file = self.output_dir / f"{category}_translations.json"

        if category_file.exists():
            try:
                with open(category_file, 'r', encoding='utf-8') as f:
                    entries = json.load(f)

                if char in entries:
                    del entries[char]

                with open(category_file, 'w', encoding='utf-8') as f:
                    json.dump(entries, f, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                pass

    def _get_answered_chars(self) -> set:
        """Get all characters that have been answered."""
        return set(self.state.get("good", []) + self.state.get("bad", []) + self.state.get("unsure", []))

    def _categorize_char(self, char: str) -> Optional[str]:
        """Find which category a character belongs to."""
        for category in ["good", "bad", "unsure"]:
            if char in self.state.get(category, []):
                return category
        return None

    def _display_entry(self, index: int, total: int, char: str, data: Dict):
        """Display an entry for review."""
        print("\n" + "=" * 60)
        print(f"Entry {index + 1}/{total}")
        print("=" * 60)
        print(f"    char: {char}")
        print(f"gloss_en: {data.get('gloss_en', 'N/A')}")
        print(f"gloss_fr: {data.get('gloss_fr', 'N/A')}")
        print("-" * 60)

    def _get_user_input(self) -> str:
        """Get user input for translation verification."""
        print("[g]ood, [b]ad, [u]nsure, [z]undo, [s]kip, [q]uit: ", end='', flush=True)

        while True:
            # Get single character input without requiring Enter
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setcbreak(fd)  # Use cbreak instead of raw for better behavior
                choice = sys.stdin.read(1).lower()
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

            if choice in ['g', 'b', 'u', 's', 'q', 'z']:
                print(choice)  # Echo the character and move to next line
                return choice
            elif choice == '\x03':  # Ctrl+C
                print()
                raise KeyboardInterrupt
            # Silently ignore other keys and wait for a valid one

    def add_entry(self, char: str, category: str) -> bool:
        """Add entry to a category."""
        if category not in ["good", "bad", "unsure"]:
            return False

        # Remove from other categories if it exists there
        old_category = self._categorize_char(char)
        if old_category and old_category != category:
            self.state[old_category].remove(char)

        # Add to new category
        if char not in self.state[category]:
            self.state[category].append(char)
            self._save_state()
            self._sync_all_category_files()
            self.history.append((char, category))
            return True
        return False

    def undo_last(self) -> bool:
        """Undo the last categorization."""
        if not self.history:
            print("Nothing to undo!")
            return False

        char, category = self.history.pop()

        if char in self.state[category]:
            self.state[category].remove(char)
            self._save_state()
            self._sync_all_category_files()
            print(f"✓ Undid: '{char}' removed from {category}")
            return True

        return False

    def run_interactive(self):
        """Run the interactive verification session."""
        answered = self._get_answered_chars()
        unanswered = [char for char in self.translations.keys() if char not in answered]

        if not unanswered:
            print("All translations have been reviewed!")
            return

        print(f"\nFound {len(unanswered)} unanswered translations.")
        print(f"(Already answered: {len(answered)})")
        print("Type 'help' for commands or start reviewing.\n")

        index = 0
        while index < len(unanswered):
            char = unanswered[index]
            self._display_entry(index, len(unanswered), char, self.translations[char])

            while True:
                user_input = self._get_user_input()

                if user_input == 'g':
                    self.add_entry(char, "good")
                    print("✓ Marked as GOOD")
                    index += 1
                    break
                elif user_input == 'b':
                    self.add_entry(char, "bad")
                    print("✗ Marked as BAD")
                    index += 1
                    break
                elif user_input == 'u':
                    self.add_entry(char, "unsure")
                    print("? Marked as UNSURE")
                    index += 1
                    break
                elif user_input in ['s', 'skip']:
                    print("⊘ Skipped")
                    index += 1
                    break
                elif user_input == 'z':
                    if self.undo_last():
                        # Go back to previous entry
                        if index > 0:
                            index -= 1
                        # Re-display the current (now previous) entry
                        break
                elif user_input == 'q':
                    self._save_state()
                    print("\n✓ Session saved. Goodbye!")
                    return

        self._save_state()
        print("\n" + "=" * 60)
        print("✓ All translations reviewed!")
        self._print_summary()

    def _print_summary(self):
        """Print summary statistics."""
        print("\nSummary:")
        print(f"    Good: {len(self.state.get('good', []))} translations")
        print(f"     Bad: {len(self.state.get('bad', []))} translations")
        print(f"  Unsure: {len(self.state.get('unsure', []))} translations")
        print(f"   Total: {sum(len(self.state.get(c, [])) for c in ['good', 'bad', 'unsure'])} / {len(self.translations)}")
        print("=" * 60)

    def show_status(self):
        """Show current review status."""
        print("\n" + "=" * 60)
        print("Translation Review Status")
        print("=" * 60)

        answered = self._get_answered_chars()
        total = len(self.translations)

        print(f"Total characters: {total}")
        print(f"Reviewed: {len(answered)} ({len(answered)/total*100:.1f}%)")
        print()
        self._print_summary()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Verify French translations of Chinese character glosses")
    parser.add_argument("--file", default="gloss_translation-qwen-max.json", help="JSON file to verify (default: gloss_translation-qwen-max.json)")
    parser.add_argument("--status", action="store_true", help="Show review status without interactive mode")

    args = parser.parse_args()

    checker = TranslationChecker(args.file)

    if args.status:
        checker.show_status()
    else:
        checker.run_interactive()


if __name__ == "__main__":
    main()
