# Alberta Frac Hub — Methodology

This note explains every cleaning and enrichment decision made in the pipeline. It is intended to be read alongside the data dictionary. Reading time: ~7 minutes.

---

## 1. Why we clean the source

The AER publishes hydraulic fracturing disclosure data as a public download, but the file is not analysis-ready. Known structural issues:

- Pipe (`|`) delimiter with a 7-row preamble and trailing footer rows
- Supplier names have dozens of spelling variants for the same company
- Ingredient names are manually entered and highly inconsistent
- Chemical concentrations are expressed at the component level, not the total fluid level
- The AER has changed the file format without notice (see Format History below)

None of these issues make the data wrong — they make it hard to use. The goal of this pipeline is to fix the structural problems without altering the underlying disclosures.

**Format history:**
- Pre-2026: Pipe-delimited, correct column order, proper dates
- March 2026: Comma-delimited, columns shifted, dates broken (00:00.0 across all rows)
- March 26 2026: Reverted to pipe-delimited with correct columns and real dates; added trailing footer rows and timestamp-format dates

---

## 2. Date parsing

**What was wrong.** The March 2026 comma-delimited export stored all dates as time-only values (00:00.0) with no date component across all 580k rows. The reverted pipe-delimited format stores dates as full timestamps: `2015-11-08 00:00:00.000`.

**What we do.** Date columns are parsed using `format="%Y-%m-%d %H:%M:%S.%f"`. Values that cannot be parsed become NaT. `start_year` and `start_month` are derived at this stage.

**Limitation.** A small number of rows have genuinely missing dates in the source. These become NaT and are excluded from date-filtered analysis.

---

## 3. Supplier canonicalization

**What was wrong.** The same service company appears under many name variants — different capitalizations, abbreviations, legal entity suffixes, and leading/trailing whitespace.

**What we do.** A lookup table at `config/supplier_name_map.csv` maps known variants to a single canonical name. Before the map lookup, `component_supplier_name` is uppercased, stripped, and whitespace-collapsed. The result is stored in `component_supplier_name_clean`. Unmatched values fall back to the uppercased raw value and are flagged as `UNMATCHED` in `supplier_flag`.

**Limitation.** The mapping table is manually maintained. New suppliers or novel name variants will not be canonicalized until added. The source monitoring script flags unmatched names on each run.

**Acquisition note.** `BAKER PETROLITE` and `BJ SERVICES` were independent companies before acquisition by Baker Hughes. They are currently mapped to `BAKER HUGHES`. Future versions may treat pre/post-acquisition records separately for historical trend analysis.

---

## 4. Ingredient name deduplication

**What was wrong.** Ingredient names are manually entered by operators. The same chemical (e.g. crystalline silica) appears under 68 different name variants across the dataset.

**What we do.** Where `cas_hmirc` is a valid CAS number (not Trade Secret or Not Available), we build a canonical name lookup: the most frequently used `ingredient_name` for each CAS number across the entire dataset. This is purely data-driven — no manual curation. The result is stored in `ingredient_name_clean` (lowercase).

Where the CAS is undisclosed, basic string normalization is applied (lowercase, strip, collapse whitespace) as a best-effort fallback.

**Coverage.** 449,904 rows (77%) deduped via CAS. 130,914 rows (23%) normalized via fallback. 1 row null (CAS `0-00-0` with no ingredient name — AER data entry error).

**Limitation.** The fallback does not collapse synonyms for undisclosed ingredients. CAS-based deduplication is definitive; fallback normalization is best-effort only.

---

## 5. Carrier fluid supplier inference

**What was wrong.** Carrier fluid rows (water, CO2, etc.) have no supplier name in the AER disclosure — operators only report suppliers for additives and proppants.

**What we do.** For carrier fluid rows only, we infer the likely supplier using the most common `component_supplier_name_clean` value from other rows on the same well. The result is stored in `carrier_fluid_supplier_inferred`. A companion `carrier_fluid_supplier_confidence` column records `HIGH` (single supplier on well) or `LOW` (multiple suppliers, majority used).

**Coverage.** 37,289 of 39,088 carrier fluid rows inferred (95%). 28,241 HIGH confidence, 9,048 LOW confidence, 1,799 null (no other supplier data on well).

**Limitation.** This is an inference, not a reported value. The original `component_supplier_name` is always null for carrier fluid rows and is never modified.

---

## 6. Concentration normalization

**What was wrong.** The raw `concentration_component` field reports each ingredient as a percentage of its parent additive product — not of the total frac fluid. You cannot directly compare chemical concentrations across wells without this correction.

**What we do.** For each well, rows are grouped by `[well_licence_number, start_date, component_trade_name, component_quantity_uom]`. Within each group, `concentration_component` values are summed and each row is divided by that sum, producing `normalized_concentration` that sums to 100% per group. `normalized_pumped_amount` is then:

```
normalized_pumped_amount = (normalized_concentration / 100) x total_component_volume_weight
```

**Limitation.** Normalization is relative within each component group, not across the entire frac fluid. For total-fluid-level analysis, use `concentration_hff` where available.

---

## 7. Formation enrichment

**What was wrong.** The frac disclosure dataset has no formation or geological zone information. A well's coordinates alone do not reliably indicate the formation being fracked — a well can target any number of formations at depth regardless of surface location.

**What we do.** A three-step join retrieves formation names from AER reference data:

1. Join frac data (`uwi`) to ST37 (`uwi_display`) to retrieve `field_code` and `pool_code`
2. Join `field_code` + `pool_code` to the ST103 FieldPoolList to retrieve `field_name`, `production_pool_name`, and `geological_pool_name`
3. `field_code` and `pool_code` are dropped from the final output — they are intermediate keys only

**Why geological_pool_name and not a basin label.** Coordinate-based basin bounding boxes are geologically inaccurate. A well in central Alberta (geographically within a "Duvernay" bounding box) may be targeting Cardium, Belly River, Viking, or dozens of other formations. `geological_pool_name` from the AER's own pool registry is the correct formation indicator. `field_centre` provides reliable regional grouping for geographic analysis and is already present in the raw frac data.

**Coverage.** ST37 join: 100% (all frac wells exist in ST37). FieldPool join: 81.7% have `field_name` and `production_pool_name`. 79.0% have `geological_pool_name` (some wells have a field/pool match but no geological pool name assigned in the AER registry). The 21% null rate is concentrated in specific fields (HUSSAR, ENTICE, WILD RIVER) where the AER has not assigned geological pool names — it is not correlated with well age.

---

## 8. Licensee canonicalization

**What was wrong.** The raw `licensee` field has the same variant problem as supplier names. Additionally, the Well Licence List appends BA codes to company names (e.g. `Ovintiv Canada ULC(A123)`).

**What we do.** The AER Well Licence List CSV is joined on `well_licence_number`. The licence number in the frac data is an integer (e.g. `2105`); the Well Licence List stores it as `W 0002105`. The join key is normalized by stripping the `W ` prefix and leading zeros. BA code suffixes are stripped from company names using a regex. The result is stored in `licensee_clean`.

**Coverage.** 100% — every licence number in the frac dataset matched the Well Licence List.

---

## 9. Known limitations and future improvements

| Limitation | Planned improvement |
|---|---|
| Supplier map is manually maintained | Semi-automated fuzzy matching to flag likely variants |
| Ingredient deduplication fallback is string-only | CAS registry lookup for additional chemical synonyms |
| 21% null geological_pool_name | Investigate alternative formation source for unmatched fields |
| No production linkage | Join to Petrinex production data in a future phase |
| Ingredient name deduplication runs on whole dataset | Incremental update logic for monthly pipeline runs |
| Carrier fluid supplier is inferred, not reported | Document in output with confidence flag — already implemented |
