#!/bin/bash
set -e

WAND_DIR="$(cd "$(dirname "$0")/.." && pwd)"

python3 - "$WAND_DIR" <<'PY'
from pathlib import Path
import sys

wand_dir = Path(sys.argv[1])
play_dir = wand_dir / "vanilla-media" / "play"

targets = [
    play_dir / "index.html",
    play_dir / "es" / "index.html",
    play_dir / "fr" / "index.html",
    play_dir / "pt" / "index.html",
]

for file_path in targets:
    if not file_path.is_file():
        continue
    text = file_path.read_text(encoding="utf-8")
    
    # Update Login button to point to /play/ruffle.html
    text = text.replace('href="/#/login"', 'href="/play/ruffle.html"')
    
    # Update external Disney & navbar links to /play/
    text = text.replace('href="http://www.clubpenguin.com/?home=return"', 'href="/play/"')
    text = text.replace('href="https://secured.clubpenguin.com/membership"', 'href="/play/"')
    text = text.replace('href="http://www.clubpenguin.com/whats-new"', 'href="/play/"')
    text = text.replace('href="http://www.clubpenguin.com/safety"', 'href="/play/"')
    text = text.replace('href="http://www.clubpenguin.com/parents"', 'href="/play/"')
    text = text.replace('href="http://www.clubpenguin.com/fun-stuff"', 'href="/play/"')
    text = text.replace('href="https://www.clubpenguinisland.com/"', 'href="/play/"')
    text = text.replace('href="http://help.disney.com/clubpenguin"', 'href="/play/"')
    text = text.replace('href="/penguin/logout"', 'href="/play/"')
    
    file_path.write_text(text, encoding="utf-8")
    print(f"Patched links in {file_path.name}")

print("Successfully applied landing page links patch.")
PY
