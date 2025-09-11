import sys
from pathlib import Path

# Ensure the project root is importable in tests without per-file hacks
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
