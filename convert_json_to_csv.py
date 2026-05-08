#!/usr/bin/env python3
"""Convert election JSON files to CSV (wide format)."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


FIXED_FIELDS = [
    "district",
    "subdistrict",
    "unit_index",
    "form_type",
    "vote_phase",
    "ballot_total",
    "ballot_valid",
    "ballot_invalid",
    "ballot_no_vote",
]


def iter_json_files(input_dir: Path) -> Iterable[Path]:
    return sorted(input_dir.glob("*.json"))


def load_records(path: Path) -> List[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        print(f"WARN: Failed to parse JSON: {path} ({exc})", file=sys.stderr)
        return []
    except OSError as exc:
        print(f"WARN: Failed to read file: {path} ({exc})", file=sys.stderr)
        return []

    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]

    print(f"WARN: Unexpected JSON structure: {path}", file=sys.stderr)
    return []


def infer_form_type(record: Dict[str, Any], path: Path) -> str:
    form_type = record.get("form_type")
    if isinstance(form_type, str) and form_type.strip():
        return form_type.strip()

    name = path.name.lower()
    if name.startswith("partylist_"):
        return "partylist"
    if name.startswith("constituency_"):
        return "constituency"

    return "unknown"


def infer_vote_phase(source_path: str) -> str:
    filename = Path(source_path).name.lower()
    if "5-16" in filename:
        return "in_district_advance"
    if "5-17" in filename:
        return "out_of_district_advance"
    return "election_day"


def normalize_score(value: Any) -> Tuple[bool, Any]:
    if value is None:
        return False, None
    if isinstance(value, bool):
        return True, int(value)
    if isinstance(value, (int, float)):
        return True, int(value)
    if isinstance(value, str):
        trimmed = value.strip()
        if trimmed == "":
            return False, None
        try:
            return True, int(trimmed)
        except ValueError:
            try:
                return True, int(float(trimmed))
            except ValueError:
                return False, None
    return False, None


def parse_location(source_file: Any) -> Tuple[str, str]:
    if not isinstance(source_file, str):
        return "", ""

    district = ""
    subdistrict = ""
    parts = source_file.replace("\\", "/").split("/")
    if parts:
        district_part = parts[0]
        if "อำเภอ" in district_part:
            district = district_part.split("อำเภอ", 1)[-1]
        filename = parts[-1]
        filename = filename.rsplit(".", 1)[0]
        if "ตำบล" in filename:
            subdistrict = filename.split("ตำบล", 1)[-1]
            subdistrict = "".join(ch for ch in subdistrict if not ch.isdigit())
            subdistrict = subdistrict.strip()
    return district, subdistrict


def collect_rows(
    input_dir: Path,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    partylist_rows: List[Dict[str, Any]] = []
    constituency_rows: List[Dict[str, Any]] = []

    for path in iter_json_files(input_dir):
        for record in load_records(path):
            record_form_type = infer_form_type(record, path)
            record["form_type"] = record_form_type
            record["_source_path"] = str(path)
            if record_form_type == "partylist":
                partylist_rows.append(record)
            elif record_form_type == "constituency":
                constituency_rows.append(record)
            else:
                print(
                    f"WARN: Unknown form_type in {path}, skipping record",
                    file=sys.stderr,
                )

    return partylist_rows, constituency_rows


def collect_score_columns(rows: List[Dict[str, Any]]) -> List[str]:
    keys = set()
    for record in rows:
        scores = record.get("scores")
        if isinstance(scores, dict):
            keys.update(scores.keys())
    return sorted(keys)


def build_row(
    record: Dict[str, Any],
    score_columns: List[str],
    missing_value: Any,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {}
    district, subdistrict = parse_location(record.get("source_file"))
    row["district"] = district
    row["subdistrict"] = subdistrict
    for field in FIXED_FIELDS:
        if field in ("district", "subdistrict"):
            continue
        if field == "vote_phase":
            row[field] = infer_vote_phase(record.get("_source_path", ""))
            continue
        row[field] = record.get(field, "")

    scores = record.get("scores")
    if not isinstance(scores, dict):
        scores = {}

    for key in score_columns:
        if key in scores:
            ok, normalized = normalize_score(scores.get(key))
            row[key] = normalized if ok else missing_value
            if not ok:
                print(
                    "WARN: Non-numeric score for "
                    f"{record.get('_source_path', 'unknown')} / {key}",
                    file=sys.stderr,
                )
        else:
            row[key] = missing_value

    return row


def write_csv(
    output_path: Path,
    rows: List[Dict[str, Any]],
    score_columns: List[str],
    missing_value: Any,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = FIXED_FIELDS + score_columns

    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in rows:
            writer.writerow(build_row(record, score_columns, missing_value))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert election JSON files to CSV (wide format)."
    )
    parser.add_argument(
        "--input-dir",
        default="electionJson",
        help="Folder containing JSON files (default: electionJson)",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Folder to write CSV files (default: current directory)",
    )
    parser.add_argument(
        "--scores-missing",
        choices=["0", "blank"],
        default="0",
        help="How to fill missing/invalid scores (default: 0)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.exists():
        print(f"ERROR: input directory not found: {input_dir}", file=sys.stderr)
        return 1

    partylist_rows, constituency_rows = collect_rows(input_dir)
    missing_value: Any = 0 if args.scores_missing == "0" else ""

    partylist_scores = collect_score_columns(partylist_rows)
    constituency_scores = collect_score_columns(constituency_rows)

    write_csv(
        output_dir / "partylist.csv",
        partylist_rows,
        partylist_scores,
        missing_value,
    )
    write_csv(
        output_dir / "constituency.csv",
        constituency_rows,
        constituency_scores,
        missing_value,
    )

    print(
        f"Wrote {len(partylist_rows)} partylist rows and "
        f"{len(constituency_rows)} constituency rows to {output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
