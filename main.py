"""Command line entry point for the Thai election OCR pipeline.

Usage:
    python main.py                     # รันทุก step
    python main.py --step split        # รันแค่ split
    python main.py --step ocr          # รันแค่ ocr (constituency + partylist)
    python main.py --step clean        # รันแค่ clean output ที่มีอยู่
    python main.py --step validate     # รันแค่ validate ทั้ง 3 layer
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

import pandas as pd

import config
from clean import clean_result
from corrections import apply_manual_corrections, load_all_corrections
from ocr import reparse_results, save_outputs, run_ocr
from paths import json_output_glob
from split import split_all
from validate import run_validate


def setup_logging() -> logging.Logger:
    """Configure file and console logging for the pipeline."""
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    file_handler = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def load_results(form_type: str) -> list[dict[str, Any]]:
    """Load saved per-source JSON results for one form type."""
    json_paths = sorted(config.OUTPUT_DIR.glob(json_output_glob(form_type)))
    if not json_paths:
        legacy_path = config.OUTPUT_DIR / config.OUTPUT_FILES[form_type]["json"]
        if legacy_path.exists():
            json_paths = [legacy_path]
        else:
            raise FileNotFoundError(
                f"Missing results files: {config.OUTPUT_DIR / json_output_glob(form_type)}"
            )

    results: list[dict[str, Any]] = []
    for json_path in json_paths:
        with json_path.open("r", encoding="utf-8") as input_file:
            data = json.load(input_file)
        if not isinstance(data, list):
            raise ValueError(f"Results file is not a list: {json_path}")
        results.extend(data)
    return results


def clean_results(
    results: list[dict[str, Any]],
    form_type: str,
    manual_corrections: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Re-parse raw OCR text and clean all result records."""
    reparsed_results = reparse_results(results, form_type)
    corrected_results = apply_manual_corrections(
        reparsed_results,
        form_type,
        manual_corrections,
    )
    return [clean_result(result) for result in corrected_results]


def count_cleaning_notes(results: list[dict[str, Any]]) -> int:
    """Count recorded cleaning notes across result records."""
    return sum(
        len(result.get(config.FIELD_CLEANING_NOTES) or []) for result in results
    )


def count_parse_success(results: list[dict[str, Any]]) -> tuple[int, int, int]:
    """Count parse-pass, parse-fail, and total records."""
    total = len(results)
    failed = sum(1 for result in results if result.get(config.FIELD_PARSE_ERROR))
    return total - failed, failed, total


def count_internal_status(
    const_results: list[dict[str, Any]],
    partylist_results: list[dict[str, Any]],
) -> tuple[int, int]:
    """Count internal validation pass/fail records."""
    all_results = [*const_results, *partylist_results]
    passed = sum(
        1 for result in all_results if result.get(config.FIELD_STATUS) == config.STATUS_PASS
    )
    failed = len(all_results) - passed
    return passed, failed


def count_cross_statuses() -> dict[str, int]:
    """Count cross-form statuses from cross_validation.csv."""
    csv_path = config.OUTPUT_DIR / config.CROSS_VALIDATION_CSV
    if not csv_path.exists():
        return {}
    dataframe = pd.read_csv(csv_path, encoding="utf-8-sig")
    counts = dataframe[config.FIELD_CROSS_STATUS].value_counts().to_dict()
    return {str(key): int(value) for key, value in counts.items()}


def count_stat_flagged(
    const_results: list[dict[str, Any]],
    partylist_results: list[dict[str, Any]],
) -> int:
    """Count records with statistical warning flags."""
    return sum(
        1
        for result in [*const_results, *partylist_results]
        if result.get(config.FIELD_STAT_FLAGS)
    )


def count_flagged_rows() -> int:
    """Count rows in flagged.csv."""
    csv_path = config.OUTPUT_DIR / config.FLAGGED_CSV
    if not csv_path.exists():
        return 0
    dataframe = pd.read_csv(csv_path, encoding="utf-8-sig")
    return int(len(dataframe))


def print_summary(
    split_summary: dict[str, int] | None = None,
    const_results: list[dict[str, Any]] | None = None,
    partylist_results: list[dict[str, Any]] | None = None,
    cleaning_count: int | None = None,
    validation_done: bool = False,
) -> None:
    """Print a compact end-of-run summary."""
    print("\n=== SUMMARY ===")
    if split_summary is not None:
        print(f"Split        : {split_summary.get('processed', 0)} files processed")

    if const_results is not None and partylist_results is not None:
        const_pass, const_fail, const_total = count_parse_success(const_results)
        party_pass, party_fail, party_total = count_parse_success(partylist_results)
        print("OCR")
        print(f"  Constituency : {const_pass} PASS / {const_fail} FAIL / {const_total} total")
        print(f"  Party-list   : {party_pass} PASS / {party_fail} FAIL / {party_total} total")

    if cleaning_count is not None:
        print(f"Cleaning     : {cleaning_count} fields auto-corrected across all records")

    if validation_done and const_results is not None and partylist_results is not None:
        internal_pass, internal_fail = count_internal_status(
            const_results,
            partylist_results,
        )
        cross_counts = count_cross_statuses()
        stat_count = count_stat_flagged(const_results, partylist_results)
        flagged_count = count_flagged_rows()
        print("Validation")
        print(f"  Internal     : {internal_pass} PASS / {internal_fail} FAIL")
        print(
            "  Cross-form   : "
            f"{cross_counts.get(config.CROSS_STATUS_OK, 0)} OK / "
            f"{cross_counts.get(config.CROSS_STATUS_MISMATCH, 0)} MISMATCH / "
            f"{cross_counts.get(config.CROSS_STATUS_MISSING_PAIR, 0)} MISSING_PAIR"
        )
        print(f"  Statistical  : {stat_count} records flagged (warnings only)")
        print(f"Flagged      : {flagged_count} records → {config.OUTPUT_DIR / config.FLAGGED_CSV}")
        print(f"Cross-val    : {config.OUTPUT_DIR / config.CROSS_VALIDATION_CSV}")
        print(f"Stat report  : {config.OUTPUT_DIR / config.STATISTICAL_REPORT_CSV}")

    print(f"Log          : {config.LOG_FILE}")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Thai election OCR pipeline")
    parser.add_argument(
        "--step",
        choices=config.STEP_CHOICES,
        default=config.DEFAULT_STEP,
        help="Pipeline step to run",
    )
    return parser.parse_args()


def main() -> None:
    """Run the requested pipeline step."""
    logger = setup_logging()
    args = parse_args()
    logger.info("Starting pipeline step: %s", args.step)

    split_summary: dict[str, int] | None = None
    const_results: list[dict[str, Any]] | None = None
    partylist_results: list[dict[str, Any]] | None = None
    cleaning_count: int | None = None
    validation_done = False
    manual_corrections = load_all_corrections()

    if args.step in (config.STEP_ALL, config.STEP_SPLIT):
        split_summary = split_all(logger)

    if args.step in (config.STEP_ALL, config.STEP_OCR):
        const_results = run_ocr(config.FORM_CONSTITUENCY)
        partylist_results = run_ocr(config.FORM_PARTYLIST)

    if args.step == config.STEP_CLEAN:
        const_results = load_results(config.FORM_CONSTITUENCY)
        partylist_results = load_results(config.FORM_PARTYLIST)

    if args.step in (config.STEP_ALL, config.STEP_CLEAN):
        if const_results is None:
            const_results = load_results(config.FORM_CONSTITUENCY)
        if partylist_results is None:
            partylist_results = load_results(config.FORM_PARTYLIST)
        const_results = clean_results(
            const_results,
            config.FORM_CONSTITUENCY,
            manual_corrections,
        )
        partylist_results = clean_results(
            partylist_results,
            config.FORM_PARTYLIST,
            manual_corrections,
        )
        save_outputs(const_results, config.FORM_CONSTITUENCY)
        save_outputs(partylist_results, config.FORM_PARTYLIST)
        cleaning_count = count_cleaning_notes([*const_results, *partylist_results])

    if args.step == config.STEP_VALIDATE:
        const_results = load_results(config.FORM_CONSTITUENCY)
        partylist_results = load_results(config.FORM_PARTYLIST)

    if args.step in (config.STEP_ALL, config.STEP_VALIDATE):
        if const_results is None:
            const_results = load_results(config.FORM_CONSTITUENCY)
        if partylist_results is None:
            partylist_results = load_results(config.FORM_PARTYLIST)
        const_results = reparse_results(const_results, config.FORM_CONSTITUENCY)
        partylist_results = reparse_results(partylist_results, config.FORM_PARTYLIST)
        const_results = apply_manual_corrections(
            const_results,
            config.FORM_CONSTITUENCY,
            manual_corrections,
        )
        partylist_results = apply_manual_corrections(
            partylist_results,
            config.FORM_PARTYLIST,
            manual_corrections,
        )
        const_results, partylist_results = run_validate(const_results, partylist_results)
        save_outputs(const_results, config.FORM_CONSTITUENCY)
        save_outputs(partylist_results, config.FORM_PARTYLIST)
        validation_done = True
        if cleaning_count is None:
            cleaning_count = count_cleaning_notes([*const_results, *partylist_results])

    logger.info("Finished pipeline step: %s", args.step)
    print_summary(
        split_summary=split_summary,
        const_results=const_results,
        partylist_results=partylist_results,
        cleaning_count=cleaning_count,
        validation_done=validation_done,
    )


if __name__ == "__main__":
    main()
