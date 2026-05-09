#!/usr/bin/env python3
"""Merge election result CSV files with polling-unit latitude/longitude data."""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path
from typing import Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_UNITS_CSV = PROJECT_ROOT / "phatthalung_polling_units_latlong_expanded.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "merged_output"

THAI_SARA_AM = "\u0e33"
THAI_SARA_AA = "\u0e32"
THAI_AMPHOE = "\u0e2d\u0e33\u0e40\u0e20\u0e2d"
THAI_TAMBON = "\u0e15\u0e33\u0e1a\u0e25"

BASE_RESULT_COLUMNS = {
    "district",
    "subdistrict",
    "unit_index",
    "form_type",
    "vote_phase",
    "ballot_total",
    "ballot_valid",
    "ballot_invalid",
    "ballot_no_vote",
}

UNIT_METADATA_COLUMNS = [
    "pdf_page",
    "pdf_sequence",
    "unit_district",
    "source_subdistrict_pdf",
    "polling_unit_no",
    "moo",
    "polling_place_pdf",
    "registered_voters_66",
    "province",
    "registrar",
    "latlong_subdistrict",
    "latlong_location",
    "latitude",
    "longitude",
    "electorate",
    "latlong_row_id",
    "latlong_match_method",
    "latlong_match_score",
    "coordinate_reused_count",
    "merge_key_subdistrict_unit",
    "latlong_merge_status",
    "latlong_result_match_method",
]

HELP_TEXT = """Examples:
  python merge_election_with_latlong.py
  python merge_election_with_latlong.py --output-dir merged_output
  python merge_election_with_latlong.py --include-full
  python merge_election_with_latlong.py --constituency-csv output/constituency.csv --partylist-csv output/partylist.csv
"""


def unique_path(path: Path) -> Path:
    """Return a non-existing path by appending _v2, _v3, ... if needed."""
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}_v{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def read_csv(path: Path) -> pd.DataFrame:
    """Read a UTF-8 CSV file."""
    return pd.read_csv(path, encoding="utf-8-sig")


def normalize_text(value: object) -> str:
    """Normalize Thai labels for robust key matching."""
    if pd.isna(value):
        return ""
    text = str(value).strip()
    text = text.replace(THAI_SARA_AM, THAI_SARA_AA)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[()（）\-.\\/|_]", "", text)
    return text.casefold()


def normalize_district(value: object) -> str:
    """Normalize district names, ignoring prefixes and district-number suffixes."""
    text = normalize_text(value)
    text = text.replace(normalize_text(THAI_AMPHOE), "")
    text = re.sub(r"\d+", "", text)
    return text


def normalize_subdistrict_fallback(value: object) -> str:
    """Build a looser subdistrict key for municipal suffix and Thai mark variants."""
    text = normalize_text(value)
    text = text.replace(normalize_text("\u0e40\u0e17\u0e28\u0e1a\u0e32\u0e25"), "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        char
        for char in text
        if not ("\u0e31" <= char <= "\u0e3a" or "\u0e47" <= char <= "\u0e4e")
    )
    return text


def extract_subdistrict_from_source_file(value: object) -> str:
    """Extract a subdistrict name from source_file when no subdistrict column exists."""
    if pd.isna(value):
        return ""
    filename = Path(str(value).replace("\\", "/")).name
    stem = filename.rsplit(".", 1)[0]
    if THAI_TAMBON in stem:
        stem = stem.split(THAI_TAMBON, 1)[-1]
    stem = re.sub(r"^\d+", "", stem)
    return stem.strip()


def resolve_default_csv(filename: str) -> Path:
    """Find a result CSV in the project root or output directory."""
    root_path = PROJECT_ROOT / filename
    output_path = PROJECT_ROOT / "output" / filename
    if root_path.exists():
        return root_path
    if output_path.exists():
        return output_path
    return root_path


def prepare_units(units: pd.DataFrame) -> pd.DataFrame:
    """Prepare polling-unit metadata and merge keys."""
    prepared = units.copy()
    prepared["unit_index"] = pd.to_numeric(prepared["unit_index"], errors="coerce")
    prepared["_merge_unit_index"] = prepared["unit_index"].astype("Int64")
    prepared["_merge_district_key"] = prepared["district"].map(normalize_district)
    prepared["_merge_subdistrict_key"] = prepared["source_subdistrict_pdf"].map(
        normalize_text
    )
    prepared["_fallback_subdistrict_key"] = prepared["source_subdistrict_pdf"].map(
        normalize_subdistrict_fallback
    )
    prepared = prepared.rename(columns={"district": "unit_district"})

    keep_columns = [
        "_merge_district_key",
        "_merge_subdistrict_key",
        "_fallback_subdistrict_key",
        "_merge_unit_index",
        *[column for column in UNIT_METADATA_COLUMNS if column in prepared.columns],
    ]
    return prepared[keep_columns].drop_duplicates()


def ensure_location_columns(results: pd.DataFrame) -> pd.DataFrame:
    """Ensure district and subdistrict columns exist for merge keys."""
    prepared = results.copy()
    if "district" not in prepared.columns:
        prepared["district"] = ""
    if "subdistrict" not in prepared.columns:
        if "source_file" in prepared.columns:
            prepared["subdistrict"] = prepared["source_file"].map(
                extract_subdistrict_from_source_file
            )
        else:
            prepared["subdistrict"] = ""
    return prepared


def merge_one_result(
    results: pd.DataFrame,
    units: pd.DataFrame,
    form_type: str,
) -> pd.DataFrame:
    """Merge one election result table with polling-unit metadata."""
    prepared = ensure_location_columns(results)
    prepared = prepared.copy()
    prepared["_result_row_id"] = range(len(prepared))
    prepared["unit_index"] = pd.to_numeric(prepared["unit_index"], errors="coerce")
    prepared["_merge_unit_index"] = prepared["unit_index"].astype("Int64")
    prepared["_merge_district_key"] = prepared["district"].map(normalize_district)
    prepared["_merge_subdistrict_key"] = prepared["subdistrict"].map(normalize_text)
    prepared["_fallback_subdistrict_key"] = prepared["subdistrict"].map(
        normalize_subdistrict_fallback
    )

    exact_key_columns = [
        "_merge_district_key",
        "_merge_subdistrict_key",
        "_merge_unit_index",
    ]
    fallback_key_columns = [
        "_merge_district_key",
        "_fallback_subdistrict_key",
        "_merge_unit_index",
    ]

    units_exact = units.drop_duplicates(subset=exact_key_columns, keep=False)
    fallback_counts = units.groupby(fallback_key_columns).size().rename("_key_count")
    units_fallback = units.merge(
        fallback_counts.reset_index(),
        on=fallback_key_columns,
        how="left",
    )
    units_fallback = units_fallback[units_fallback["_key_count"] == 1].drop(
        columns=["_key_count"]
    )

    exact_lookup = {
        tuple(row[column] for column in exact_key_columns): row
        for _, row in units_exact.iterrows()
    }
    fallback_lookup = {
        tuple(row[column] for column in fallback_key_columns): row
        for _, row in units_fallback.iterrows()
    }

    merged_rows = []
    unit_value_columns = [
        column
        for column in units.columns
        if column
        not in {
            "_merge_district_key",
            "_merge_subdistrict_key",
            "_fallback_subdistrict_key",
            "_merge_unit_index",
        }
    ]

    for _, row in prepared.iterrows():
        output = row.to_dict()
        exact_key = tuple(row[column] for column in exact_key_columns)
        fallback_key = tuple(row[column] for column in fallback_key_columns)
        matched_unit = exact_lookup.get(exact_key)
        status = "matched"
        method = "exact_key"
        if matched_unit is None:
            matched_unit = fallback_lookup.get(fallback_key)
            method = "fallback_unique_subdistrict_key"
        if matched_unit is None:
            status = "unmatched"
            method = ""

        for column in unit_value_columns:
            output[column] = matched_unit[column] if matched_unit is not None else pd.NA
        output["latlong_merge_status"] = status
        output["latlong_result_match_method"] = method
        merged_rows.append(output)

    merged = pd.DataFrame(merged_rows)
    merged["form_type"] = merged.get("form_type", form_type).fillna(form_type)
    merged = merged.drop(
        columns=[
            "_merge_district_key",
            "_merge_subdistrict_key",
            "_fallback_subdistrict_key",
            "_merge_unit_index",
            "_result_row_id",
        ],
        errors="ignore",
    )
    return merged


def score_columns(dataframe: pd.DataFrame) -> list[str]:
    """Find vote score columns in a wide election result table."""
    excluded = set(BASE_RESULT_COLUMNS) | set(UNIT_METADATA_COLUMNS)
    excluded.update(
        {
            "unit_district",
            "source_subdistrict_pdf",
            "polling_unit_no",
            "moo",
            "polling_place_pdf",
            "registered_voters_66",
            "province",
            "registrar",
            "latlong_subdistrict",
            "latlong_location",
            "latitude",
            "longitude",
            "electorate",
            "latlong_row_id",
            "latlong_match_method",
            "latlong_match_score",
            "coordinate_reused_count",
            "merge_key_subdistrict_unit",
            "latlong_merge_status",
            "latlong_result_match_method",
        }
    )
    return [column for column in dataframe.columns if column not in excluded]


def to_long_format(dataframe: pd.DataFrame, form_type: str) -> pd.DataFrame:
    """Convert a wide result table to one row per candidate/party score."""
    value_columns = score_columns(dataframe)
    id_columns = [column for column in dataframe.columns if column not in value_columns]
    long = dataframe.melt(
        id_vars=id_columns,
        value_vars=value_columns,
        var_name="candidate_or_party",
        value_name="votes",
    )
    long["form_type"] = form_type
    long["votes"] = pd.to_numeric(long["votes"], errors="coerce").fillna(0).astype(int)
    ballot_valid = pd.to_numeric(long["ballot_valid"], errors="coerce")
    long["vote_share"] = long["votes"].where(ballot_valid > 0, 0) / ballot_valid.where(
        ballot_valid > 0
    )
    long["vote_share"] = long["vote_share"].fillna(0)
    return long


def to_minimal_wide_format(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Keep only map-ready location columns, ballot fields, and vote columns."""
    base_columns = [
        "district",
        "subdistrict",
        "unit_index",
        "form_type",
        "vote_phase",
        "latitude",
        "longitude",
        "latlong_location",
        "ballot_total",
        "ballot_valid",
        "ballot_invalid",
        "ballot_no_vote",
    ]
    columns = [column for column in base_columns if column in dataframe.columns]
    columns.extend(score_columns(dataframe))
    return dataframe[columns].copy()


def build_unmatched_report(dataframes: Iterable[pd.DataFrame]) -> pd.DataFrame:
    """Build a report of election rows that did not receive lat/long."""
    reports = []
    for dataframe in dataframes:
        unmatched = dataframe[
            dataframe["latlong_merge_status"].astype(str) != "matched"
        ].copy()
        if unmatched.empty:
            continue
        columns = [
            column
            for column in [
                "form_type",
                "vote_phase",
                "district",
                "subdistrict",
                "unit_index",
                "ballot_total",
                "ballot_valid",
                "latlong_merge_status",
            ]
            if column in unmatched.columns
        ]
        reports.append(unmatched[columns])
    if reports:
        return pd.concat(reports, ignore_index=True)
    return pd.DataFrame(
        columns=[
            "form_type",
            "vote_phase",
            "district",
            "subdistrict",
            "unit_index",
            "ballot_total",
            "ballot_valid",
            "latlong_merge_status",
        ]
    )


def write_output(dataframe: pd.DataFrame, path: Path) -> Path:
    """Write a CSV file without overwriting an existing file."""
    output_path = unique_path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Merge election result CSVs with polling-unit lat/long data.",
        epilog=HELP_TEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--constituency-csv",
        type=Path,
        default=resolve_default_csv("constituency.csv"),
        help="Path to constituency.csv",
    )
    parser.add_argument(
        "--partylist-csv",
        type=Path,
        default=resolve_default_csv("partylist.csv"),
        help="Path to partylist.csv",
    )
    parser.add_argument(
        "--units-csv",
        type=Path,
        default=DEFAULT_UNITS_CSV,
        help="Path to phatthalung_polling_units_latlong_expanded.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Folder for merged CSV outputs",
    )
    parser.add_argument(
        "--include-full",
        action="store_true",
        help="Also write full audit-style merged CSV files",
    )
    return parser.parse_args()


def main() -> int:
    """Run the merge workflow."""
    args = parse_args()

    constituency = read_csv(args.constituency_csv)
    partylist = read_csv(args.partylist_csv)
    units = prepare_units(read_csv(args.units_csv))

    constituency_merged = merge_one_result(
        constituency,
        units,
        form_type="constituency",
    )
    partylist_merged = merge_one_result(
        partylist,
        units,
        form_type="partylist",
    )

    constituency_minimal = to_minimal_wide_format(constituency_merged)
    partylist_minimal = to_minimal_wide_format(partylist_merged)
    constituency_long = to_long_format(constituency_minimal, "constituency")
    partylist_long = to_long_format(partylist_minimal, "partylist")
    combined_long = pd.concat([constituency_long, partylist_long], ignore_index=True)
    unmatched_report = build_unmatched_report(
        [constituency_merged, partylist_merged]
    )

    output_dir = args.output_dir
    written_paths = [
        write_output(
            constituency_minimal,
            output_dir / "constituency_with_latlong_minimal.csv",
        ),
        write_output(
            partylist_minimal,
            output_dir / "partylist_with_latlong_minimal.csv",
        ),
        write_output(
            combined_long,
            output_dir / "election_results_with_latlong_long_minimal.csv",
        ),
        write_output(
            unmatched_report,
            output_dir / "latlong_merge_unmatched_report.csv",
        ),
    ]
    if args.include_full:
        written_paths.extend(
            [
                write_output(
                    constituency_merged,
                    output_dir / "constituency_with_latlong_full.csv",
                ),
                write_output(
                    partylist_merged,
                    output_dir / "partylist_with_latlong_full.csv",
                ),
            ]
        )

    print("=== MERGE SUMMARY ===")
    print(f"Constituency rows: {len(constituency_merged)}")
    print(
        "  matched/unmatched: "
        f"{(constituency_merged['latlong_merge_status'] == 'matched').sum()} / "
        f"{(constituency_merged['latlong_merge_status'] != 'matched').sum()}"
    )
    print(f"Party-list rows   : {len(partylist_merged)}")
    print(
        "  matched/unmatched: "
        f"{(partylist_merged['latlong_merge_status'] == 'matched').sum()} / "
        f"{(partylist_merged['latlong_merge_status'] != 'matched').sum()}"
    )
    print(f"Long rows         : {len(combined_long)}")
    print(f"Unmatched report  : {len(unmatched_report)} rows")
    print("Files written:")
    for path in written_paths:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
