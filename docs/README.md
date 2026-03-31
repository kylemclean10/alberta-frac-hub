# Alberta Frac Hub

A cleaned, enriched, and continuously monitored dataset of hydraulic fracturing chemical and water use disclosures for Alberta, Canada — built on public AER data and designed for engineers, analysts, and researchers.

> **Plain language summary:** Every hydraulic fracturing operation in Alberta must disclose the chemicals and water volumes used. The Alberta Energy Regulator (AER) publishes this data, but it arrives messy — inconsistent formatting, supplier name variants, parsing artifacts, and no standardized concentration basis. This project cleans, enriches, and structures that data so it can actually be used for analysis.

---

## What's in this repo

| Item | Description |
|---|---|
| `scripts/` | Python pipeline: ingest, normalize, enrich, monitor |
| `data/sample/` | Sample rows from the raw AER dataset |
| `data/raw/` | Raw source files (not committed — see below) |
| `config/` | Supplier name mapping and other reference files |
| `docs/` | Data dictionary and methodology note |

---

## The data

### Primary source

The AER publishes hydraulic fracturing chemical and water use disclosures at the well level. Each row in the raw dataset represents a single chemical ingredient within a single additive used in a single frac job. One well can have hundreds of rows.

**Known source issues:**
- The raw file uses pipe (`|`) delimiters with a 7-row preamble and trailing footer rows
- Supplier and ingredient names have dozens of spelling variants for the same company or chemical
- Concentration values are reported at the component level, not the total fluid level
- The AER has changed the file format without notice — a schema drift monitor is included

This project monitors the source for schema changes and documents any deviations. See `docs/source_monitoring.md` for details.

**Download:** [AER Hydraulic Fracturing Fluid Data](https://www.aer.ca/data-and-performance-reports/activity-and-data/lists-and-activities/hydraulic-fracture-fluid-data)

### Reference sources (Phase 2 enrichment)

| Source | File | Used for |
|---|---|---|
| AER ST37 | `ST37.txt` | UWI to field code and pool code |
| AER ST103 | `FieldPoolList.xlsx` | Field/pool codes to formation names |
| AER ST104 | `LicenseeAgent_Codes.xlsx` | Licensee code reference |
| AER Well Licence List | `well_licence_list.csv` | Licence number to canonical company name |

**Download ST37:** [ST37 List of Wells in Alberta](https://www.aer.ca/data-and-performance-reports/statistical-reports/st37)
**Download ST103:** [ST103 Field and Pool Codes](https://www.aer.ca/data-and-performance-reports/statistical-reports/st103)
**Download Well Licence List:** [ST1 — Well Licence List for all of Alberta](https://www.aer.ca/data-and-performance-reports/statistical-reports/st1)

Place all reference files in the appropriate subfolder under `data/raw/` before running `3_enrich.py`.

---

### Schema (raw AER columns)

| Column | Type | Notes |
|---|---|---|
| Well Licence Number | string | AER well identifier |
| Last Submission Date | date | Date of most recent disclosure update |
| Licensee | string | Operating company name (raw, uncleaned) |
| Field Centre | string | AER field centre jurisdiction |
| UWI | string | Unique Well Identifier |
| Well Name | string | Operator-assigned well name |
| Number of Stages | integer | Frac stages completed |
| Bottom Hole Latitude | float | WGS84 coordinate |
| Bottom Hole Longitude | float | WGS84 coordinate |
| Production Fluid Type | string | Crude oil, gas, etc. |
| Max True Vertical Depth | float | metres |
| Total Water Volume | float | m3 |
| Start Date | date | Frac job start |
| End Date | date | Frac job end |
| Component Type | string | Carrier Fluid, Additive, Proppant |
| Component Trade Name | string | Commercial product name |
| Component Quantity UOM | string | Unit of measure for component volume |
| Total Component Volume or Weight | float | Total quantity of component used |
| Component Supplier Name | string | Raw supplier name (uncleaned) |
| Additive Purpose | string | Functional role (e.g. Breaker, Crosslinker) |
| Ingredient Name | string | Chemical ingredient name (manually entered) |
| CAS # HMIRC # | string | Chemical identifier |
| Concentration Component | float | % of this ingredient within the component |
| Concentration HFF | float | % of this ingredient within the total frac fluid |

### Enriched columns (added by pipeline)

**Added by `1_ingest_clean.py`:**

| Column | Description |
|---|---|
| `start_year` | Derived from start_date |
| `start_month` | Derived from start_date |
| `component_supplier_name_clean` | Canonicalized supplier name via supplier map |
| `supplier_flag` | UNMATCHED or null |
| `ingredient_name_clean` | CAS-deduped canonical ingredient name (lowercase) |
| `carrier_fluid_supplier_inferred` | Inferred supplier for carrier fluid rows |
| `carrier_fluid_supplier_confidence` | HIGH, LOW, or null |

**Added by `2_normalize.py`:**

| Column | Description |
|---|---|
| `pumped_amount` | Absolute quantity of ingredient pumped |
| `normalized_concentration` | Ingredient concentration normalized to 100% per component group |
| `normalized_pumped_amount` | Pumped amount on normalized concentration basis |

**Added by `3_enrich.py`:**

| Column | Description | Coverage |
|---|---|---|
| `field_name` | Field name from ST37/FieldPoolList join | 81.7% |
| `production_pool_name` | Production pool name | 81.7% |
| `geological_pool_name` | Geological formation name — primary analytical field | 79.0% |
| `licensee_clean` | Canonical company name from Well Licence List | 100% |

---

## Pipeline

```
Raw AER CSV
    |
    v
1_ingest_clean.py       -> Hydraulic_Fracturing_Clean.csv        (31 columns)
    |
    v
2_normalize.py          -> Hydraulic_Fracturing_Normalized.csv   (34 columns)
    |
    v
3_enrich.py             -> Hydraulic_Fracturing_Enriched.csv     (38 columns)
```

Each script is independent and can be run on its own. The monitor script can be run at any time against a new raw download before ingesting.

### Step 1 — Ingest and clean

```bash
python scripts/1_ingest_clean.py
python scripts/1_ingest_clean.py --input SummaryChemical-WaterUse.csv
```

- Reads pipe-delimited raw AER export, skips 7-row preamble and trailing footer rows
- Standardizes column headers and renames to snake_case
- Parses date fields (YYYY-MM-DD HH:MM:SS.mmm format)
- Canonicalizes supplier names using `config/supplier_name_map.csv`
- Deduplicates ingredient names using CAS number as the canonical key
- Infers carrier fluid suppliers from other rows on the same well
- Flags data quality issues without removing rows

### Step 2 — Normalize

```bash
python scripts/2_normalize.py
```

- Calculates absolute pumped amount per ingredient per component
- Normalizes concentration within groups of [well, date, product, UOM]
- Outputs one row per ingredient with both raw and normalized values

### Step 3 — Enrich

```bash
python scripts/3_enrich.py
```

- Joins ST37 on UWI to get field and pool codes
- Joins FieldPoolList on field/pool codes to get formation names
- Joins Well Licence List on licence number to get canonical company names
- Requires reference files in `data/raw/ST37/`, `data/raw/st103/`, `data/raw/well_licence_list.csv`

### Monitor

```bash
python scripts/monitor_source.py --save    # first run — saves baseline
python scripts/monitor_source.py           # subsequent runs — compares to baseline
```

- Checks delimiter, preamble markers, header position, column names and order
- Flags row count changes, null rate spikes, and unmatched supplier names
- Exit code 1 if any drift is detected

---

## Quickstart

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/alberta-frac-hub.git
cd alberta-frac-hub

# 2. Install dependencies
pip install -r requirements.txt

# 3. Download and place data files
#    Primary: data/raw/SummaryChemical-WaterUse.csv
#    ST37:    data/raw/ST37/ST37.txt
#    ST103:   data/raw/st103/FieldPoolList.xlsx
#    WLL:     data/raw/well_licence_list.csv

# 4. Run the monitor first
python scripts/monitor_source.py --save

# 5. Run the pipeline
python scripts/1_ingest_clean.py
python scripts/2_normalize.py
python scripts/3_enrich.py
```

---

## Key design decisions

**Why normalize to HFF basis?**
The raw AER data reports chemical concentrations as a percentage within each additive product — not as a percentage of the total fluid. Normalizing to the hydraulic fracturing fluid (HFF) basis makes cross-well and cross-product comparisons meaningful. See `docs/methodology.md` for the full calculation.

**Why deduplicate ingredient names by CAS number?**
Ingredient names are manually entered by operators and have hundreds of spelling variants for the same chemical. The CAS number is reliably reported and used as the canonical key — the most frequently occurring name for each CAS number becomes the canonical ingredient name across the dataset.

**Why use geological_pool_name instead of a basin label?**
A well's surface coordinates do not reliably indicate the formation being fracked — a well drilled in one geographic area may target any number of formations at depth. `geological_pool_name` from the AER's own pool registry is the accurate formation indicator. `field_centre` provides reliable regional grouping for geographic analysis.

**Why a supplier name map?**
The same supplier appears under dozens of name variants. The `config/supplier_name_map.csv` file maps known variants to a single canonical name. It is maintained manually and contributions are welcome.

**Why monitor the source?**
The AER changed their file format in early 2026 without notice, breaking dates across the entire dataset. The monitor script detects format changes before they silently corrupt the pipeline. See `docs/source_monitoring.md`.

---

## Repo structure

```
alberta-frac-hub/
├── data/
│   ├── raw/
│   │   ├── ST37/                        <- AER well list (not committed)
│   │   ├── st103/                       <- Field/pool/formation codes (not committed)
│   │   ├── st104/                       <- Licensee codes (not committed)
│   │   ├── SummaryChemical-WaterUse.csv <- Primary AER source (not committed)
│   │   └── well_licence_list.csv        <- AER well licence list (not committed)
│   ├── processed/                       <- Pipeline outputs (not committed)
│   └── sample/                          <- Small sample CSV (committed)
├── scripts/
│   ├── utils/
│   │   ├── paths.py                     <- Centralised path definitions
│   │   └── schema.py                    <- Column names, format constants
│   ├── 1_ingest_clean.py
│   ├── 2_normalize.py
│   ├── 3_enrich.py
│   └── monitor_source.py
├── config/
│   └── supplier_name_map.csv
├── docs/
│   ├── data_dictionary.md
│   ├── methodology.md
│   └── source_monitoring.md
├── .gitignore
├── README.md
└── requirements.txt
```

---

## Roadmap

- [x] Phase 1 — Cleaned pipeline + documentation
- [x] Phase 2 — Enrichment (formation mapping, canonical operators)
- [ ] Phase 3 — Snowflake ETL pipeline
- [ ] Phase 4 — Power BI template
- [ ] Phase 5 — Web application
- [ ] Phase 6 — AI-powered natural language query layer

---

## Docs

- [`docs/data_dictionary.md`](docs/data_dictionary.md) — Full column definitions, types, and notes
- [`docs/methodology.md`](docs/methodology.md) — Cleaning and enrichment decisions explained
- [`docs/source_monitoring.md`](docs/source_monitoring.md) — How schema drift is detected

---

## About

Built by [Kyle McLean](https://linkedin.com/in/mclean-kyle/) — data, analytics, and AI consultant based in Calgary, Alberta.

This project is independent and not affiliated with the Alberta Energy Regulator.

---

## License

MIT License. Data sourced from the AER is subject to the AER's own terms of use.
