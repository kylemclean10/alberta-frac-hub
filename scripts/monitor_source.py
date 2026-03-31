"""
scripts/monitor_source.py

Checks the AER hydraulic fracturing CSV for schema drift and structural changes.
Run this each time you download a new copy of the source file before ingesting it.

Usage:
    python scripts/monitor_source.py
    python scripts/monitor_source.py --input SummaryChemical-WaterUse.csv
    python scripts/monitor_source.py --input SummaryChemical-WaterUse.csv --baseline config/baseline_schema.json --save

Exit codes:
    0 = no issues detected
    1 = drift detected (warnings printed; review before ingesting)
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# ── Paths ──────────────────────────────────────────────────────────────────
PROJECT_ROOT    = Path(__file__).resolve().parents[1]
DATA_RAW        = PROJECT_ROOT / "data" / "raw"
CONFIG          = PROJECT_ROOT / "config"
BASELINE_PATH   = CONFIG / "baseline_schema.json"

# ── Known file structure ───────────────────────────────────────────────────
EXPECTED_PREAMBLE_ROWS = 7          # rows before the header row
EXPECTED_HEADER_ROW    = 7          # 0-indexed row index of the header
EXPECTED_DELIMITER     = ","

EXPECTED_COLUMNS = [
    "Well Licence Number",
    "Last Submission Date",
    "Licensee",
    "Field Centre",
    "UWI",
    "Well Name",
    "Number of Stages",
    "Bottom Hole Latitude",
    "Bottom Hole Longitude",
    "Production Fluid Type",
    "Max True Vertical Depth",
    "Total Water Volume",
    "Start Date",
    "End Date",
    "Component Type",
    "Component Trade Name",
    "Component Supplier Name",
    "Additive Purpose",
    "Ingredient Name",
    "CAS # HMIRC #",
    "Concentration Component",
    "Concentration HFF",
]

EXPECTED_PREAMBLE_MARKERS = [
    "AER",
    "Disclaimer",
    "Hydraulic Fracturing Summary Chemical and Water Use Data",
]


# ══════════════════════════════════════════════════════════════════════════
# Checks
# ══════════════════════════════════════════════════════════════════════════

def check_delimiter(path: Path) -> list[str]:
    issues = []
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        first_data_line = ""
        for i, line in enumerate(f):
            if i >= EXPECTED_PREAMBLE_ROWS + 1:  # skip preamble, read first data row
                first_data_line = line
                break
    if EXPECTED_DELIMITER not in first_data_line:
        issues.append(
            f"DELIMITER: Expected '{EXPECTED_DELIMITER}' but it was not found in first data row. "
            f"File may use a different delimiter."
        )
    return issues


def check_preamble(path: Path) -> list[str]:
    issues = []
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        preamble_lines = [next(f, "").strip() for _ in range(EXPECTED_PREAMBLE_ROWS)]

    for marker in EXPECTED_PREAMBLE_MARKERS:
        if not any(marker in line for line in preamble_lines):
            issues.append(f"PREAMBLE: Expected marker not found in first {EXPECTED_PREAMBLE_ROWS} rows: '{marker}'")

    return issues


def find_header_row(path: Path) -> int | None:
    """Scan up to 20 rows to find the actual header row."""
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        for i, line in enumerate(f):
            if i > 20:
                break
            if "Well Licence Number" in line:
                return i
    return None


def check_header_position(path: Path) -> tuple[list[str], int | None]:
    issues = []
    actual_row = find_header_row(path)
    if actual_row is None:
        issues.append(
            "HEADER: Could not find 'Well Licence Number' in the first 20 rows. "
            "The file structure may have changed significantly."
        )
        return issues, None
    if actual_row != EXPECTED_HEADER_ROW:
        issues.append(
            f"HEADER POSITION: Expected header on row {EXPECTED_HEADER_ROW} (0-indexed) "
            f"but found it on row {actual_row}. Preamble length may have changed."
        )
    return issues, actual_row


def check_columns(path: Path, header_row: int) -> list[str]:
    issues = []
    df = pd.read_csv(
        path,
        skiprows=header_row,
        nrows=0,
        encoding="utf-8-sig",
        low_memory=False,
    )
    actual_cols = [c.strip() for c in df.columns.tolist()]

    # Strip trailing empty columns (AER sometimes adds blank trailing cols)
    actual_cols_clean = [c for c in actual_cols if c]

    missing  = [c for c in EXPECTED_COLUMNS if c not in actual_cols_clean]
    added    = [c for c in actual_cols_clean if c not in EXPECTED_COLUMNS]

    if missing:
        issues.append(f"COLUMNS MISSING: {missing}")
    if added:
        issues.append(f"COLUMNS ADDED: {added}")

    # Check column order for the expected columns that are present
    present_expected = [c for c in EXPECTED_COLUMNS if c in actual_cols_clean]
    present_actual   = [c for c in actual_cols_clean if c in EXPECTED_COLUMNS]
    if present_expected != present_actual:
        issues.append(
            f"COLUMN ORDER CHANGED: Expected order differs from actual order for shared columns."
        )

    return issues, actual_cols_clean


def check_row_count(path: Path, header_row: int, baseline: dict) -> list[str]:
    issues = []
    df = pd.read_csv(
        path,
        skiprows=header_row,
        encoding="utf-8-sig",
        low_memory=False,
    )
    row_count = len(df)

    if "row_count" in baseline:
        prev = baseline["row_count"]
        delta = row_count - prev
        pct   = (delta / prev * 100) if prev else 0
        if delta < 0:
            issues.append(
                f"ROW COUNT DECREASED: {prev:,} → {row_count:,} ({delta:,} rows, {pct:.1f}%). "
                f"Data may have been removed from the source."
            )
        elif pct > 50:
            issues.append(
                f"ROW COUNT LARGE INCREASE: {prev:,} → {row_count:,} (+{delta:,} rows, +{pct:.1f}%). "
                f"Verify this is expected (e.g. a large backfill)."
            )
        else:
            print(f"  Row count: {prev:,} → {row_count:,} (+{delta:,} rows) ✓")
    else:
        print(f"  Row count: {row_count:,} (no baseline to compare)")

    return issues, row_count


def check_null_rates(path: Path, header_row: int, baseline: dict) -> list[str]:
    issues = []
    df = pd.read_csv(
        path,
        skiprows=header_row,
        encoding="utf-8-sig",
        low_memory=False,
    )

    critical_cols = [
        "Well Licence Number",
        "Licensee",
        "Component Type",
        "Ingredient Name",
        "Concentration Component",
    ]

    null_rates = {}
    for col in critical_cols:
        if col in df.columns:
            rate = df[col].isna().mean()
            null_rates[col] = round(rate, 4)

            if "null_rates" in baseline and col in baseline["null_rates"]:
                prev_rate = baseline["null_rates"][col]
                delta = rate - prev_rate
                if delta > 0.05:
                    issues.append(
                        f"NULL RATE SPIKE: '{col}' null rate increased from "
                        f"{prev_rate:.1%} to {rate:.1%} (+{delta:.1%}). "
                        f"May indicate a data quality regression."
                    )

    return issues, null_rates


def check_new_suppliers(path: Path, header_row: int, baseline: dict, supplier_map_path: Path) -> list[str]:
    issues = []
    df = pd.read_csv(
        path,
        skiprows=header_row,
        encoding="utf-8-sig",
        low_memory=False,
        usecols=["Component Supplier Name"],
    )

    raw_suppliers = set(
        df["Component Supplier Name"].dropna().str.upper().str.strip().unique()
    )

    known_variants = set()
    if supplier_map_path.exists():
        map_df = pd.read_csv(supplier_map_path)
        known_variants = set(map_df["Variant"].str.upper().str.strip().tolist())

    known_canonicals = set()
    if supplier_map_path.exists():
        known_canonicals = set(map_df["Canonical"].str.upper().str.strip().tolist())

    known_all = known_variants | known_canonicals

    unmatched = sorted(raw_suppliers - known_all)
    if unmatched:
        issues.append(
            f"UNMATCHED SUPPLIERS ({len(unmatched)} new): {unmatched[:10]}"
            + (" ... (truncated)" if len(unmatched) > 10 else "")
        )

    return issues


def compute_file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ══════════════════════════════════════════════════════════════════════════
# Baseline
# ══════════════════════════════════════════════════════════════════════════

def load_baseline(path: Path) -> dict:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def save_baseline(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n  Baseline saved to: {path}")


# ══════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════

def run(input_path: Path, baseline_path: Path, save: bool):
    print(f"\n{'='*60}")
    print(f"  Alberta Frac Hub — Source Monitor")
    print(f"  File:    {input_path.name}")
    print(f"  Run at:  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    if not input_path.exists():
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)

    baseline = load_baseline(baseline_path)
    all_issues = []

    # 1. File hash (detect identical re-download)
    file_hash = compute_file_hash(input_path)
    if baseline.get("file_hash") == file_hash:
        print("  File hash: unchanged (same file as baseline) ✓")
    else:
        print(f"  File hash: changed ✓" if baseline else f"  File hash: {file_hash[:16]}... (no baseline)")

    # 2. Delimiter
    print("\n  Checking delimiter...")
    issues = check_delimiter(input_path)
    all_issues += issues
    if not issues:
        print("  Delimiter: comma ✓")

    # 3. Preamble
    print("\n  Checking preamble...")
    issues = check_preamble(input_path)
    all_issues += issues
    if not issues:
        print(f"  Preamble: all markers found ✓")

    # 4. Header row position
    print("\n  Checking header position...")
    issues, header_row = check_header_position(input_path)
    all_issues += issues
    if header_row is not None and not issues:
        print(f"  Header row: {header_row} (0-indexed) ✓")
    if header_row is None:
        print("\nCannot continue — header row not found.")
        _print_summary(all_issues)
        sys.exit(1)

    # 5. Columns
    print("\n  Checking columns...")
    issues, actual_cols = check_columns(input_path, header_row)
    all_issues += issues
    if not issues:
        print(f"  Columns: all {len(EXPECTED_COLUMNS)} expected columns present ✓")

    # 6. Row count
    print("\n  Checking row count...")
    issues, row_count = check_row_count(input_path, header_row, baseline)
    all_issues += issues

    # 7. Null rates
    print("\n  Checking null rates on critical columns...")
    issues, null_rates = check_null_rates(input_path, header_row, baseline)
    all_issues += issues
    if not issues:
        print(f"  Null rates: within expected range ✓")

    # 8. Unmatched suppliers
    supplier_map = CONFIG / "supplier_name_map.csv"
    print("\n  Checking for unmatched supplier names...")
    issues = check_new_suppliers(input_path, header_row, baseline, supplier_map)
    all_issues += issues
    if not issues:
        print(f"  Supplier names: all matched ✓")

    # ── Save baseline ──────────────────────────────────────────────────
    if save:
        new_baseline = {
            "file_hash":    file_hash,
            "checked_at":   datetime.now().isoformat(),
            "source_file":  input_path.name,
            "header_row":   header_row,
            "columns":      actual_cols,
            "row_count":    row_count,
            "null_rates":   null_rates,
        }
        save_baseline(baseline_path, new_baseline)

    _print_summary(all_issues)
    sys.exit(1 if all_issues else 0)


def _print_summary(issues: list[str]):
    print(f"\n{'='*60}")
    if not issues:
        print("  RESULT: No drift detected. Safe to ingest.")
    else:
        print(f"  RESULT: {len(issues)} issue(s) detected. Review before ingesting.\n")
        for i, issue in enumerate(issues, 1):
            print(f"  [{i}] {issue}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor AER source file for schema drift.")
    parser.add_argument("--input",    type=str, default="SummaryChemical-WaterUse (4) - sample.csv",
                        help="Raw input filename (in data/raw/)")
    parser.add_argument("--baseline", type=str, default=str(BASELINE_PATH),
                        help="Path to baseline JSON file")
    parser.add_argument("--save",     action="store_true",
                        help="Save current file state as the new baseline after checking")
    args = parser.parse_args()

    run(
        input_path    = DATA_RAW / args.input,
        baseline_path = Path(args.baseline),
        save          = args.save,
    )
