# Phatthalung-District2-Election-Analysis

Tools for converting election JSON files to CSV for analysis.

## Convert JSON to CSV

The script reads all JSON files in `electionJson/` and outputs two wide-format CSV files:

- `partylist.csv`
- `constituency.csv`

Each row represents one unit, with party/candidate scores expanded into columns.
Location columns are derived from `source_file` and split into:

- `district` (อำเภอ)
- `subdistrict` (ตำบล)

### Usage

```bash
python convert_json_to_csv.py
```

### Options

```bash
python convert_json_to_csv.py --input-dir electionJson --output-dir . --scores-missing 0
```

- `--input-dir`: folder containing JSON files (default: `electionJson`)
- `--output-dir`: output folder for CSV files (default: current directory)
- `--scores-missing`: fill missing/invalid scores with `0` or leave blank (`blank`)

### Output Columns

Fixed columns (always present):

- `district`, `subdistrict`, `unit_index`, `form_type`
- `ballot_total`, `ballot_valid`, `ballot_invalid`, `ballot_no_vote`

Score columns are the union of all keys in `scores` across files.