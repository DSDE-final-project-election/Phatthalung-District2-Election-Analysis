"""Validate cleaned election OCR results."""

from __future__ import annotations

import copy
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

import config
from clean import clean_result


def _ensure_output_dir() -> None:
    """Create the configured output directory if needed."""
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _as_issue_list(value: Any) -> list[str]:
    """Normalize issue fields into a list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _numeric_values(result: dict[str, Any]) -> list[tuple[str, Any]]:
    """Collect ballot and score values with labels."""
    values: list[tuple[str, Any]] = [
        (field_name, result.get(field_name)) for field_name in config.BALLOT_FIELDS
    ]
    scores = result.get(config.FIELD_SCORES) or {}
    values.extend((f"scores['{name}']", value) for name, value in scores.items())
    return values


def validate_internal(result: dict[str, Any]) -> dict[str, Any]:
    """Validate consistency inside one OCR record."""
    updated_result = copy.deepcopy(result)
    issues = _as_issue_list(updated_result.get(config.FIELD_ISSUES))

    parse_error = updated_result.get(config.FIELD_PARSE_ERROR)
    if parse_error:
        issues.append(f"parse_error: {parse_error}")

    ballot_values = [updated_result.get(field_name) for field_name in config.BALLOT_FIELDS]
    if all(value is not None for value in ballot_values):
        ballot_sum = (
            updated_result[config.FIELD_BALLOT_VALID]
            + updated_result[config.FIELD_BALLOT_INVALID]
            + updated_result[config.FIELD_BALLOT_NO_VOTE]
        )
        if ballot_sum != updated_result[config.FIELD_BALLOT_TOTAL]:
            issues.append(
                "ballot_valid + ballot_invalid + ballot_no_vote "
                "does not equal ballot_total"
            )

    scores = updated_result.get(config.FIELD_SCORES) or {}
    score_values = list(scores.values())
    if score_values and all(value is not None for value in score_values):
        if sum(score_values) != updated_result.get(config.FIELD_BALLOT_VALID):
            issues.append("sum(scores.values()) does not equal ballot_valid")

    for label, value in _numeric_values(updated_result):
        if value is None:
            issues.append(f"{label} is None")
        elif isinstance(value, (int, float)) and value < 0:
            issues.append(f"{label} is negative")

    if updated_result.get(config.FIELD_BALLOT_TOTAL) == 0:
        issues.append("ballot_total is zero")

    updated_result[config.FIELD_ISSUES] = issues
    updated_result[config.FIELD_STATUS] = (
        config.STATUS_FAIL if issues else config.STATUS_PASS
    )
    return updated_result


def _result_key(result: dict[str, Any]) -> tuple[str, int]:
    """Build the cross-form matching key for one result."""
    return (
        str(result.get(config.FIELD_SOURCE_FILE)),
        int(result.get(config.FIELD_UNIT_INDEX)),
    )


def validate_cross_form(
    const_results: list[dict[str, Any]],
    partylist_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Validate constituency and party-list totals by source file and unit."""
    _ensure_output_dir()
    const_by_key = {_result_key(result): result for result in const_results}
    party_by_key = {_result_key(result): result for result in partylist_results}
    records: list[dict[str, Any]] = []

    for key in sorted(set(const_by_key) | set(party_by_key)):
        source_file, unit_index = key
        const_result = const_by_key.get(key)
        party_result = party_by_key.get(key)
        const_total = (
            const_result.get(config.FIELD_BALLOT_TOTAL) if const_result else None
        )
        party_total = (
            party_result.get(config.FIELD_BALLOT_TOTAL) if party_result else None
        )
        issues: list[str] = []

        if const_result is None or party_result is None:
            cross_status = config.CROSS_STATUS_MISSING_PAIR
            issues.append("matching form record not found")
            diff = None
        elif const_total == party_total:
            cross_status = config.CROSS_STATUS_OK
            diff = 0
        else:
            cross_status = config.CROSS_STATUS_MISMATCH
            diff = (
                const_total - party_total
                if isinstance(const_total, int) and isinstance(party_total, int)
                else None
            )
            issues.append("ballot_total differs between forms")

        for result in (const_result, party_result):
            if result is not None:
                result[config.FIELD_CROSS_STATUS] = cross_status
                result[config.FIELD_CROSS_ISSUES] = issues.copy()

        records.append(
            {
                config.FIELD_SOURCE_FILE: source_file,
                config.FIELD_UNIT_INDEX: unit_index,
                "const_ballot_total": const_total,
                "partylist_ballot_total": party_total,
                "diff": diff,
                config.FIELD_CROSS_STATUS: cross_status,
                config.FIELD_CROSS_ISSUES: config.CSV_JOIN_SEPARATOR.join(issues),
            }
        )

    dataframe = pd.DataFrame(records, columns=config.CROSS_VALIDATION_COLUMNS)
    dataframe.to_csv(
        config.OUTPUT_DIR / config.CROSS_VALIDATION_CSV,
        index=False,
        encoding="utf-8-sig",
    )
    return records


def _std(values: list[float]) -> float:
    """Calculate sample standard deviation for outlier checks."""
    if len(values) < 2:
        return 0.0
    standard_deviation = float(scipy_stats.tstd(values))
    if np.isnan(standard_deviation):
        return 0.0
    return standard_deviation


def _registered_voters(source_file: str, unit_index: int) -> int | None:
    """Find registered voters for a unit from optional config."""
    voters = config.REGISTERED_VOTERS_BY_UNIT
    tuple_key = (source_file, unit_index)
    colon_key = f"{source_file}:{unit_index}"
    nested_value = voters.get(source_file)

    if tuple_key in voters:
        return voters[tuple_key]
    if colon_key in voters:
        return voters[colon_key]
    if isinstance(nested_value, dict):
        return nested_value.get(unit_index) or nested_value.get(str(unit_index))
    return None


def _write_statistical_report(records: list[dict[str, Any]]) -> None:
    """Write statistical validation records to CSV."""
    _ensure_output_dir()
    dataframe = pd.DataFrame(records, columns=config.STATISTICAL_REPORT_COLUMNS)
    dataframe.to_csv(
        config.OUTPUT_DIR / config.STATISTICAL_REPORT_CSV,
        index=False,
        encoding="utf-8-sig",
    )


def validate_statistical(
    results: list[dict[str, Any]],
    form_type: str,
) -> list[dict[str, Any]]:
    """Flag statistical outliers and anomalies across a full dataset."""
    names_list = config.FORM_NAMES[form_type]
    for result in results:
        existing_flags = result.get(config.FIELD_STAT_FLAGS) or []
        result[config.FIELD_STAT_FLAGS] = (
            existing_flags if isinstance(existing_flags, list) else [str(existing_flags)]
        )

    totals = [
        result.get(config.FIELD_BALLOT_TOTAL)
        for result in results
        if isinstance(result.get(config.FIELD_BALLOT_TOTAL), int)
    ]
    if totals:
        median_total = float(np.median(totals))
        std_total = _std([float(value) for value in totals])
        if std_total > 0:
            for result in results:
                total = result.get(config.FIELD_BALLOT_TOTAL)
                if isinstance(total, int) and abs(total - median_total) > 3 * std_total:
                    result[config.FIELD_STAT_FLAGS].append("ballot_total_outlier")

    for result in results:
        ballot_valid = result.get(config.FIELD_BALLOT_VALID)
        scores = result.get(config.FIELD_SCORES) or {}
        if isinstance(ballot_valid, int) and ballot_valid > 0:
            for name, score in scores.items():
                if isinstance(score, int) and score > 0.95 * ballot_valid:
                    result[config.FIELD_STAT_FLAGS].append(
                        f"single_party_dominance: {name}"
                    )

    for name in names_list:
        values = [
            result.get(config.FIELD_SCORES, {}).get(name)
            for result in results
            if isinstance(result.get(config.FIELD_SCORES, {}).get(name), int)
        ]
        if not values:
            continue
        median_score = float(np.median(values))
        std_score = _std([float(value) for value in values])
        if std_score <= 0:
            continue
        for result in results:
            score = result.get(config.FIELD_SCORES, {}).get(name)
            if isinstance(score, int) and abs(score - median_score) > 3 * std_score:
                result[config.FIELD_STAT_FLAGS].append(f"score_outlier: {name}")

    records: list[dict[str, Any]] = []
    for result in results:
        source_file = str(result.get(config.FIELD_SOURCE_FILE))
        unit_index = int(result.get(config.FIELD_UNIT_INDEX))
        ballot_total = result.get(config.FIELD_BALLOT_TOTAL)
        registered_voters = _registered_voters(source_file, unit_index)
        turnout: float | None = None

        if isinstance(ballot_total, int) and registered_voters:
            turnout = ballot_total / registered_voters
            if turnout > 1:
                result[config.FIELD_STAT_FLAGS].append("turnout_over_100")
            elif turnout < 0.10:
                result[config.FIELD_STAT_FLAGS].append("turnout_suspiciously_low")

        records.append(
            {
                config.FIELD_SOURCE_FILE: source_file,
                config.FIELD_UNIT_INDEX: unit_index,
                config.FIELD_FORM_TYPE: form_type,
                config.FIELD_BALLOT_TOTAL: ballot_total,
                config.FIELD_BALLOT_VALID: result.get(config.FIELD_BALLOT_VALID),
                config.FIELD_TURNOUT: turnout,
                config.FIELD_STAT_FLAGS: config.CSV_JOIN_SEPARATOR.join(
                    result.get(config.FIELD_STAT_FLAGS) or []
                ),
            }
        )

    _write_statistical_report(records)
    return records


def _write_flagged_csv(results: list[dict[str, Any]]) -> None:
    """Write validation failures to flagged.csv."""
    _ensure_output_dir()
    rows: list[dict[str, Any]] = []
    for result in results:
        issues = [
            *_as_issue_list(result.get(config.FIELD_ISSUES)),
            *_as_issue_list(result.get(config.FIELD_CROSS_ISSUES)),
        ]
        rows.append(
            {
                config.FIELD_SOURCE_FILE: result.get(config.FIELD_SOURCE_FILE),
                config.FIELD_UNIT_INDEX: result.get(config.FIELD_UNIT_INDEX),
                config.FIELD_FORM_TYPE: result.get(config.FIELD_FORM_TYPE),
                config.FIELD_STATUS: result.get(config.FIELD_STATUS),
                config.FIELD_CROSS_STATUS: result.get(config.FIELD_CROSS_STATUS),
                config.FIELD_ISSUES: config.CSV_JOIN_SEPARATOR.join(issues),
                config.FIELD_STAT_FLAGS: config.CSV_JOIN_SEPARATOR.join(
                    result.get(config.FIELD_STAT_FLAGS) or []
                ),
            }
        )

    dataframe = pd.DataFrame(rows)
    dataframe.to_csv(
        config.OUTPUT_DIR / config.FLAGGED_CSV,
        index=False,
        encoding="utf-8-sig",
    )


def run_validate(
    const_results: list[dict[str, Any]],
    partylist_results: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run cleaning, internal, cross-form, and statistical validation."""
    cleaned_const_results = [clean_result(result) for result in const_results]
    cleaned_partylist_results = [clean_result(result) for result in partylist_results]

    validated_const_results = [
        validate_internal(result) for result in cleaned_const_results
    ]
    validated_partylist_results = [
        validate_internal(result) for result in cleaned_partylist_results
    ]

    validate_cross_form(validated_const_results, validated_partylist_results)
    const_stat_records = validate_statistical(
        validated_const_results,
        config.FORM_CONSTITUENCY,
    )
    party_stat_records = validate_statistical(
        validated_partylist_results,
        config.FORM_PARTYLIST,
    )
    _write_statistical_report([*const_stat_records, *party_stat_records])

    all_results = [*validated_const_results, *validated_partylist_results]
    failed_results = [
        result
        for result in all_results
        if result.get(config.FIELD_STATUS) != config.STATUS_PASS
        or result.get(config.FIELD_CROSS_STATUS) != config.CROSS_STATUS_OK
    ]
    _write_flagged_csv(failed_results)
    return validated_const_results, validated_partylist_results
