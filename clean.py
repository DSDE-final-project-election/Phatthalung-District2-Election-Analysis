"""Clean OCR results before validation."""

from __future__ import annotations

import copy
import re
from typing import Any

import config


def clean_number(value: str | int | None) -> tuple[int | None, str | None]:
    """Convert an OCR value into an int with a short cleaning note."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value, None
    if value is None:
        return None, None

    original = str(value)
    cleaned = original
    notes: list[str] = []

    translated = cleaned.translate(config.THAI_DIGIT_TRANSLATION)
    if translated != cleaned:
        cleaned = translated
        notes.append("thai digit")

    for source, replacement in config.OCR_CONFUSION_MAP.items():
        if source in cleaned:
            cleaned = cleaned.replace(source, replacement)
            notes.append(f"{source}→{replacement} substitution")

    compacted = re.sub(r"[\s,]", "", cleaned)
    if compacted != cleaned:
        removed: list[str] = []
        if "," in cleaned:
            removed.append("comma")
        if re.search(r"\s", cleaned):
            removed.append("space")
        cleaned = compacted
        notes.append(f"removed {' and '.join(removed)}")

    if cleaned in config.DASH_VALUES:
        return 0, "dash treated as zero"

    if cleaned.isdigit() or (cleaned.startswith("-") and cleaned[1:].isdigit()):
        parsed = int(cleaned)
        if notes:
            return parsed, config.CSV_JOIN_SEPARATOR.join(notes)
        return parsed, None

    return None, f"parse failed: {original}"


def clean_scores(scores: dict[str, Any]) -> tuple[dict[str, int | None], list[str]]:
    """Clean all score values in a score dictionary."""
    cleaned_scores: dict[str, int | None] = {}
    notes: list[str] = []

    for name, raw_value in scores.items():
        cleaned_value, note = clean_number(raw_value)
        cleaned_scores[name] = cleaned_value
        if note:
            notes.append(
                f"scores['{name}']: {raw_value!r} → {cleaned_value} ({note})"
            )

    return cleaned_scores, notes


def clean_ballot_fields(result: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Clean top-level ballot count fields in one result."""
    updated_result = copy.deepcopy(result)
    notes: list[str] = []

    for field_name in config.BALLOT_FIELDS:
        raw_value = updated_result.get(field_name)
        cleaned_value, note = clean_number(raw_value)
        updated_result[field_name] = cleaned_value
        if note:
            notes.append(
                f"{field_name}: {raw_value!r} → {cleaned_value} ({note})"
            )

    return updated_result, notes


def clean_result(result: dict[str, Any]) -> dict[str, Any]:
    """Clean ballot fields and scores, then attach cleaning notes."""
    updated_result, ballot_notes = clean_ballot_fields(result)
    raw_scores = updated_result.get(config.FIELD_SCORES) or {}
    cleaned_scores, score_notes = clean_scores(raw_scores)

    existing_notes = updated_result.get(config.FIELD_CLEANING_NOTES) or []
    if not isinstance(existing_notes, list):
        existing_notes = [str(existing_notes)]

    updated_result[config.FIELD_SCORES] = cleaned_scores
    updated_result[config.FIELD_CLEANING_NOTES] = (
        existing_notes + ballot_notes + score_notes
    )
    return updated_result
