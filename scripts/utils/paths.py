"""
utils/paths.py

Single source of truth for all project paths.
Every script imports from here — never hardcode paths elsewhere.
"""

from pathlib import Path

PROJECT_ROOT  = Path(__file__).resolve().parents[2]
DATA_RAW      = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_SAMPLE   = PROJECT_ROOT / "data" / "sample"
CONFIG        = PROJECT_ROOT / "config"
OUTPUTS       = PROJECT_ROOT / "outputs"
