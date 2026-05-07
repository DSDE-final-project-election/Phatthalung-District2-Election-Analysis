"""Apply optional manual corrections before validation."""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any

import config
from paths import json_output_glob


def _load_correction_records(path: Path) -> list[dict[str, Any]]:
    """Load correction records from one JSON file."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as input_file:
        corrections = json.load(input_file)
    if not isinstance(corrections, list):
        raise ValueError(f"Manual corrections must be a list: {path}")
    for correction in corrections:
        if not isinstance(correction, dict):
            raise ValueError(f"Manual correction must be an object: {correction!r}")
    return corrections


def load_manual_corrections(path: Path = config.MANUAL_CORRECTIONS_FILE) -> list[dict[str, Any]]:
    """Load manual correction records if the file exists."""
    return _load_correction_records(path)


def load_correction_output_files(
    corrections_dir: Path = config.CORRECTIONS_DIR,
) -> list[dict[str, Any]]:
    """Load edited per-source output JSON files from output/corrections."""
    if not corrections_dir.exists():
        return []

    records: list[dict[str, Any]] = []
    for form_type in config.FORM_TYPES:
        for json_path in sorted(corrections_dir.rglob(json_output_glob(form_type))):
            records.extend(_load_correction_records(json_path))
    return records


def load_all_corrections() -> list[dict[str, Any]]:
    """Load both compact corrections and edited output JSON corrections."""
    return [
        *load_manual_corrections(),
        *load_correction_output_files(),
    ]


def _correction_key(record: dict[str, Any]) -> tuple[str, str, int]:
    """Build the lookup key for a result or correction record."""
    return (
        str(record[config.FIELD_FORM_TYPE]),
        str(record[config.FIELD_SOURCE_FILE]),
        int(record[config.FIELD_UNIT_INDEX]),
    )


def _clear_validation_fields(result: dict[str, Any]) -> None:
    """Remove validation fields that must be recomputed after correction."""
    for field_name in (
        config.FIELD_STATUS,
        config.FIELD_CROSS_STATUS,
        config.FIELD_CROSS_ISSUES,
        config.FIELD_STAT_FLAGS,
        config.FIELD_CLEANING_NOTES,
        config.FIELD_ISSUES,
    ):
        result.pop(field_name, None)


def _apply_one_correction(
    result: dict[str, Any],
    correction: dict[str, Any],
) -> dict[str, Any]:
    """Apply one correction object to one OCR result."""
    updated_result = copy.deepcopy(result)
    for field_name in config.BALLOT_FIELDS:
        if field_name in correction:
            updated_result[field_name] = correction[field_name]

    if config.FIELD_SCORES in correction:
        corrected_scores = correction[config.FIELD_SCORES]
        if not isinstance(corrected_scores, dict):
            raise ValueError(f"scores correction must be an object: {correction!r}")
        scores = copy.deepcopy(updated_result.get(config.FIELD_SCORES) or {})
        scores.update(corrected_scores)
        updated_result[config.FIELD_SCORES] = scores

    if config.FIELD_PARSE_ERROR in correction:
        updated_result[config.FIELD_PARSE_ERROR] = correction[config.FIELD_PARSE_ERROR]

    notes = updated_result.get("manual_correction_notes") or []
    if not isinstance(notes, list):
        notes = [str(notes)]
    notes.append("manual correction applied")
    updated_result["manual_correction_notes"] = notes
    _clear_validation_fields(updated_result)
    return updated_result


def apply_manual_corrections(
    results: list[dict[str, Any]],
    form_type: str,
    corrections: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Apply manual corrections for one form type."""
    active_corrections = corrections if corrections is not None else load_manual_corrections()
    correction_by_key: dict[tuple[str, str, int], dict[str, Any]] = {}

    for correction in active_corrections:
        if correction.get(config.FIELD_FORM_TYPE) != form_type:
            continue
        correction_by_key[_correction_key(correction)] = correction

    if not correction_by_key:
        return results

    updated_results: list[dict[str, Any]] = []
    applied_count = 0
    for result in results:
        key = _correction_key(result)
        correction = correction_by_key.get(key)
        if correction:
            updated_results.append(_apply_one_correction(result, correction))
            applied_count += 1
        else:
            updated_results.append(result)

    logging.getLogger(__name__).info(
        "Applied %s manual correction(s) for %s",
        applied_count,
        form_type,
    )
    return updated_results
