#!/bin/bash
set -e

WAND_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PENGUIN_FILE="$WAND_DIR/houdini/houdini/data/penguin.py"

python3 - "$PENGUIN_FILE" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()

original_safe_nickname = """    def safe_nickname(self, language_bitmask):
        return self.nickname if self.approval & language_bitmask else "P" + str(self.id)"""

fixed_safe_nickname = """    def safe_nickname(self, language_bitmask):
        return self.nickname"""

original_approval = """    @cached_property
    def approval(self):
        return int(f'{self.approval_ru * 1}{self.approval_de * 1}0{self.approval_es * 1}'
                   f'{self.approval_fr * 1}{self.approval_pt * 1}{self.approval_en * 1}', 2)"""

fixed_approval = """    @cached_property
    def approval(self):
        return 127"""

if fixed_approval in text and fixed_safe_nickname in text:
    print("penguin.py is already patched for nickname approval.")
else:
    if original_safe_nickname in text:
        text = text.replace(original_safe_nickname, fixed_safe_nickname, 1)
    if original_approval in text:
        text = text.replace(original_approval, fixed_approval, 1)
    path.write_text(text)
    print("Successfully patched penguin.py for automatic nickname approval.")
PY