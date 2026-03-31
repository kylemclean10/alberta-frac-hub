# Alberta Frac Hub — Data Dictionary

This document defines every column in the Alberta Frac Hub dataset, organized by stage in the pipeline. Use this as the authoritative reference for field names, types, valid values, and known data quality issues.

---

## 1. Raw AER columns

These columns come directly from the AER hydraulic fracturing chemical and water use disclosure file. No transformations have been applied. Known source issues are noted per field.

| Column name | Renamed to | Data type | Description | Known issues |
|---|---|---|---|---|
| Well Licence Number | `Well_Licence_Number` | string | AER-assigned licence number for the well. Primary identifier for grouping rows to a single frac job. | Leading zeros may be dropped by spreadsheet tools. Always treat as string. |
| Last Submission Date | `Last_Submission_Date` | date | Date the operator last updated this disclosure. A well may be resubmitted after corrections. | Raw export stores this as a time value (e.g. `37:37.6`) in some versions. Requires parsing. |
| Licensee | `Licensee` | string | Name of the operating company holding the well licence. | Not normalized — same company may appear under multiple name variants. |
| Field Centre | `Field_Centre` | string | AER regional field centre with jurisdiction over the well. | — |
| UWI | `UWI` | string | Unique Well Identifier. Standard 16-character Canadian well identifier. | Format: `CC/LL-SS-TTT-RRW/S`. Some rows use shorthand. |
| Well Name | `Well_Name` | string | Operator-assigned well name. | Not standardized across operators. |
| Number of Stages | `Number_of_Stages` | integer | Number of hydraulic fracturing stages completed. | Null in some older submissions. |
| Bottom Hole Latitude | `Bottom_Hole_Latitude` | float | WGS84 latitude of the well's bottom hole location. | — |
| Bottom Hole Longitude | `Bottom_Hole_Longitude` | float | WGS84 longitude of the well's bottom hole location. | — |
| Production Fluid Type | `Production_Fluid_Type` | string | Target production type. Common values: `CRUDE OIL`, `GAS`, `BITUMEN`. | Trailing whitespace common in raw data. |
| Max True Vertical Depth | `Max_True_Vertical_Depth` | float | Maximum true vertical depth of the well in metres. | Reported as `NULL` in many rows. |
| Total Water Volume | `Total_Water_Volume` | float | Total water volume used in the frac job, in m³. Populated only on the carrier fluid row. | Zero on non-carrier-fluid rows. Must aggregate carefully. |
| Start Date | `Start_Date` | date | Date the frac job began. | Same parsing artifact as Last Submission Date in some exports. |
| End Date | `End_Date` | date | Date the frac job ended. | Same parsing artifact as Last Submission Date in some exports. |
| Component Type | `Component_Type` | string | Classification of the component. Values: `Carrier Fluid`, `Additive`, `Proppant`. | — |
| Component Trade Name | `Component_Trade_Name` | string | Commercial product name of the additive or proppant. | Null for carrier fluid rows. Spelling varies across operators for the same product. |
| Component Supplier Name | `Component_Supplier_Name` | string | Raw supplier name as submitted by the operator. | Highly inconsistent. See `Component_Supplier_Name_Clean`. |
| Component Quantity UOM | `Component_Quantity_UOM` | string | Unit of measure for the component volume or weight. Common values: `Litres`, `kg`, `Metric Tonnes`, `m3`. | Inconsistent capitalization and abbreviation. |
| Total Component Volume or Weight | `Total_Component_Volume_or_Weight` | float | Total quantity of this component used in the frac job, in the unit specified by `Component_Quantity_UOM`. | — |
| Additive Purpose | `Additive_Purpose` | string | Functional role of the additive. Examples: `Breaker`, `Crosslinker`, `Clay Control`, `Gelling Agent`, `Surfactant`, `Bactericide/Biocide`. | Null for carrier fluid and proppant rows. |
| Ingredient Name | `Ingredient_Name` | string | Chemical ingredient name as submitted. | Significant variation in naming for the same chemical. See `Ingredient_Name_Clean`. |
| CAS # HMIRC # | `CAS_HMIRC` | string | Chemical Abstracts Service (CAS) number or HMIRC identifier. | Value `Not Available` used when CAS is undisclosed. Not always a valid CAS format. |
| Concentration Component | `Concentration_Component` | float | Concentration of this ingredient as a percentage of its parent component (additive or proppant). Rows for the same component should sum to ~100%. | Does not represent concentration in the total frac fluid. See `Concentration_HFF` and `Normalized_Concentration`. |
| Concentration HFF | `Concentration_HFF` | float | Concentration of this ingredient as a percentage of the total hydraulic fracturing fluid (HFF). Provided by the operator in some submissions. | Not consistently populated across all wells or years. Use `Normalized_Concentration` for cross-well comparisons. |

---

## 2. Derived columns (added by pipeline)

These columns are calculated by the pipeline scripts and appended to the cleaned dataset. They do not exist in the raw AER file.

| Column name | Added by | Data type | Description | Calculation |
|---|---|---|---|---|
| `Start_Year` | `1_ingest_clean.py` | integer | Calendar year extracted from `Start_Date`. Used for time-series filtering and aggregation. | `pd.to_datetime(Start_Date).dt.year` |
| `Start_Month` | `1_ingest_clean.py` | integer | Calendar month (1–12) extracted from `Start_Date`. | `pd.to_datetime(Start_Date).dt.month` |
| `Component_Supplier_Name_Clean` | `1_ingest_clean.py` | string | Canonicalized supplier name. All variants mapped to a single standardized name via `config/supplier_name_map.csv`. Uppercased and stripped of whitespace. | Lookup against `supplier_name_map.csv`; fallback to uppercased raw value if no match. |
| `Ingredient_Name_Clean` | `4_product_BOM_analysis.py` | string | Lowercased, stripped, and deduplicated ingredient name. Common non-hazardous ingredient variants are collapsed to a single value. | String normalization + explicit replacement map for known variants (e.g. `non-hazardous ingredients` → `non hazardous ingredients`). |
| `Pumped_Amount` | `2_normalize.py` | float | Absolute quantity of this ingredient pumped, in the same unit as `Total_Component_Volume_or_Weight`. | `Total_Component_Volume_or_Weight × (Concentration_Component / 100)` |
| `Normalized_Concentration` | `2_normalize.py` | float | Ingredient concentration as a percentage of the total volume/weight of its parent component group within the well, normalized to sum to 100% per group. See methodology note for grouping definition. | Sum of `Concentration_Component` within group; each row divided by group sum × 100. |
| `Normalized_Pumped_Amount` | `2_normalize.py` | float | Pumped amount recalculated using `Normalized_Concentration`. Comparable across wells. | `(Normalized_Concentration / 100) × Total_Component_Volume_or_Weight` |

---

## 3. Analysis output columns

These columns appear in the generated report files in `outputs/`. They are not part of the cleaned dataset.

### Component_And_Supplier_Pumped_Totals.xlsx

**Sheet: Component_Totals**

| Column name | Description |
|---|---|
| `Component_Trade_Name` | Commercial product name |
| `Normalized_Pumped_Amount` | Total normalized pumped amount across all wells in the dataset |
| `Market_Share_%` | This product's share of total pumped volume across all products |

**Sheet: Supplier_Totals**

| Column name | Description |
|---|---|
| `Component_Supplier_Name_Clean` | Canonical supplier name |
| `Normalized_Pumped_Amount` | Total normalized pumped amount across all wells in the dataset |
| `Market_Share_%` | This supplier's share of total pumped volume across all suppliers |

**Sheet: Supplier_Component_Totals**

| Column name | Description |
|---|---|
| `Component_Supplier_Name_Clean` | Canonical supplier name |
| `Component_Trade_Name` | Commercial product name |
| `Normalized_Pumped_Amount` | Total normalized pumped amount for this supplier-product pair |

### Product_Formulation_Table.xlsx

| Column name | Description |
|---|---|
| `Component_Trade_Name` | Commercial product name |
| `Component_Supplier_Name_Clean` | Canonical supplier name |
| `Component_Quantity_UOM` | Unit of measure for this product |
| `Additive_Purpose` | Functional role of the additive |
| `Ingredient_Name_Clean` | Cleaned ingredient name |
| `CAS_HMIRC` | Chemical identifier |
| `Normalized_Concentration` | Average normalized concentration of this ingredient across all wells where this product was used |

---

## 4. Config reference files

### config/supplier_name_map.csv

Maps raw supplier name variants to a single canonical name. Used by `1_ingest_clean.py` during ingestion.

| Column | Description |
|---|---|
| `Variant` | Raw supplier name as it appears in the AER data. Case-insensitive match. |
| `Canonical` | Standardized supplier name. Uppercase. Used in `Component_Supplier_Name_Clean`. |

**Example rows:**

| Variant | Canonical |
|---|---|
| Trican Well Service | TRICAN WELL SERVICE |
| TRICAN | TRICAN WELL SERVICE |
| trican well service ltd | TRICAN WELL SERVICE |

To add a new variant, append a row to this file. No code changes required.

---

## Notes on concentration fields

The dataset contains three related concentration fields. Understanding the difference is important for correct analysis.

**`Concentration_Component`** — as reported by the operator. This is the percentage of an ingredient *within its parent additive product*. It does not tell you how much of the ingredient ended up in the total frac fluid.

**`Concentration_HFF`** — also operator-reported, but expressed as a percentage of the *total hydraulic fracturing fluid*. More useful for cross-well comparisons, but inconsistently populated across the dataset.

**`Normalized_Concentration`** — calculated by this pipeline. Expresses each ingredient's concentration relative to the total volume of its component group within the well. Consistent and comparable across all wells. Use this field for any analysis that compares chemical use across wells, operators, or time periods.

See `docs/methodology.md` for the full calculation and design rationale.

---

## 5. Phase 2 enrichment columns

These columns are added by `3_enrich.py` and appear only in `Hydraulic_Fracturing_Enriched.csv`.

| Column name | Added by | Data type | Description | Coverage |
|---|---|---|---|---|
| `field_name` | `3_enrich.py` | string | Field name from the AER ST37/FieldPoolList join. Identifies the named field the well belongs to (e.g. REDWATER, HUSSAR). | 81.7% |
| `production_pool_name` | `3_enrich.py` | string | Production pool name from FieldPoolList. More specific than field name. | 81.7% |
| `geological_pool_name` | `3_enrich.py` | string | Geological pool name from FieldPoolList. The primary formation indicator — use this for formation-based analysis. | 79.0% |
| `licensee_clean` | `3_enrich.py` | string | Canonical company name from the AER Well Licence List. BA code suffixes stripped. Join key normalized from `W 0002105` format to `2105`. | 100% |

### Notes on formation coverage

79% of rows have a `geological_pool_name`. The 21% null rate is not correlated with well age — it is concentrated in specific fields (HUSSAR, ENTICE, WILD RIVER, ROCKYFORD) where the AER has not assigned geological pool names in the FieldPoolList. These fields are primarily in central Alberta (Midnapore, Drayton Valley, Red Deer field centres).

### Why no basin column

A coordinate-based basin label was evaluated and rejected. A well's surface or bottom hole coordinates do not reliably indicate the formation being fracked — the same geographic area can have wells targeting many different formations at different depths. `geological_pool_name` is the accurate formation indicator. `field_centre` (already in the raw data) provides reliable regional grouping for geographic analysis.

---

## 6. Reference data sources (Phase 2)

These files are used by `3_enrich.py` to enrich the dataset. They are not committed to the repo — download links are in the README.

### data/raw/ST37/ST37.txt

AER ST37 List of Wells in Alberta. Tab-delimited, ~659k rows. Used to retrieve field and pool codes by UWI.

| Column (index) | Description |
|---|---|
| 0 — `uwi_display` | UWI in display format — join key to frac dataset |
| 4 — `field_code` | Numeric field code — join key to FieldPoolList |
| 5 — `pool_code` | Numeric pool code — join key to FieldPoolList |

### data/raw/st103/FieldPoolList.xlsx

AER ST103 Field and Pool Codes. 68,241 rows. Maps field/pool codes to human-readable names.

| Column | Description |
|---|---|
| `Field Code` | Numeric field code |
| `Production Pool Code` | Numeric pool code |
| `Field Name` | Human-readable field name |
| `Production Pool Name` | Human-readable production pool name |
| `Geological Pool Name` | Geological pool name — primary formation indicator |

### data/raw/well_licence_list.csv

AER Well Licence List for all of Alberta. ~538k rows, updated daily. Maps licence numbers to canonical company names.

| Column | Description |
|---|---|
| `01.Licence Number` | Licence number in `W 0002105` format |
| `02.Company Name` | Company name with BA code suffix (e.g. `Ovintiv Canada ULC(A123)`) |

**Note:** `licensee_clean` is derived by stripping the `W ` prefix and leading zeros from the licence number, and stripping the BA code suffix from the company name.
