#!/bin/bash
set -e

WAND_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOGIN_FILE="$WAND_DIR/houdini/houdini/handlers/login/login.py"

python3 - "$LOGIN_FILE" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()

broken = """    password_correct = True

                                                  password.encode('utf-8'), data.password.encode('utf-8'))
"""

fixed = """    password_correct = await loop.run_in_executor(None, bcrypt.checkpw,
                                                  password.encode('utf-8'), data.password.encode('utf-8'))
"""

if fixed in text:
    print("login.py is already fixed.")
elif broken in text:
    path.write_text(text.replace(broken, fixed, 1))
    print("login.py fixed.")
else:
    raise SystemExit(
        "Expected original login.py pattern was not found; refusing to modify the file."
    )
PY
