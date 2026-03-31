"""
utils/schema.py

Column definitions, renames, and known constants for the AER source file.
Update here when the AER changes their schema — nowhere else.

FORMAT HISTORY:
- Pre 2026-03: Pipe-delimited, correct column order, proper dates
- 2026-03:     Comma-delimited, columns shifted left (supplier removed),
               dates broken (00:00.0 time-only values)
- 2026-03-26:  Reverted to pipe-delimited, correct column order, proper dates
               New: trailing footer rows (rows affected + completion time)
               New: well_licence_number has leading/trailing spaces
               New: date format is YYYY-MM-DD HH:MM:SS.mmm
"""

# ── Source file structure ──────────────────────────────────────────────────
PREAMBLE_ROWS = 7
ENCODING      = "utf-8-sig"
DELIMITER     = "|"

# ── Date format ───────────────────────────────────────────────────────────
DATE_FORMAT = "%Y-%m-%d %H:%M:%S.%f"

# ── Raw column names → clean snake_case names ─────────────────────────────
COLUMN_RENAME = {
    "Well Licence Number":              "well_licence_number",
    "Last Submission Date":             "last_submission_date",
    "Licensee":                         "licensee",
    "Field Centre":                     "field_centre",
    "UWI":                              "uwi",
    "Well Name":                        "well_name",
    "Number of Stages":                 "number_of_stages",
    "Bottom Hole Latitude":             "bottom_hole_latitude",
    "Bottom Hole Longitude":            "bottom_hole_longitude",
    "Production Fluid Type":            "production_fluid_type",
    "Max True Vertical Depth":          "max_true_vertical_depth",
    "Total Water Volume":               "total_water_volume",
    "Start Date":                       "start_date",
    "End Date":                         "end_date",
    "Component Type":                   "component_type",
    "Component Trade Name":             "component_trade_name",
    "Component Quantity UOM":           "component_quantity_uom",
    "Total Component Volume or Weight": "total_component_volume_weight",
    "Component Supplier Name":          "component_supplier_name",
    "Additive Purpose":                 "additive_purpose",
    "Ingredient Name":                  "ingredient_name",
    "CAS # HMIRC #":                    "cas_hmirc",
    "Concentration Component":          "concentration_component",
    "Concentration HFF":                "concentration_hff",
}

# ── Columns that should be treated as strings, not inferred ───────────────
STRING_COLUMNS = [
    "Well Licence Number",
    "UWI",
    "CAS # HMIRC #",
]

# ── Date columns to parse ─────────────────────────────────────────────────
DATE_COLUMNS = [
    "Last Submission Date",
    "Start Date",
    "End Date",
]

# ── NULL sentinel values used by the AER ─────────────────────────────────
AER_NULL_VALUES = ["NULL", "null", "Null", "", " "]

# ── CAS values that indicate undisclosed ingredients ─────────────────────
UNDISCLOSED_CAS = {
    "Trade Secret",
    "trade secret",
    "Not Available",
    "not available",
}

# ── Footer row detection ──────────────────────────────────────────────────
# The new pipe-delimited format includes trailing footer rows after data:
#   blank line
#   (581800 rows affected)
#   blank line
#   Completion time: 2026-03-26T15:48:48...
# These are filtered out by checking that well_licence_number is numeric.
WELL_LICENCE_PATTERN = r"^\s*\d+\s*$"
