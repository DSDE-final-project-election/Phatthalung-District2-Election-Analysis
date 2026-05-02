"""Path helpers for raw, processed, and output election files."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

import config


def iter_raw_pdfs() -> list[Path]:
    """Return all raw PDFs, including PDFs inside district subfolders."""
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(path for path in config.RAW_DIR.rglob("*.pdf") if path.is_file())


def raw_relative_path(raw_pdf_path: Path) -> Path:
    """Return a raw PDF path relative to the raw data directory."""
    return Path(raw_pdf_path).relative_to(config.RAW_DIR)


def processed_pdf_path(raw_pdf_path: Path, form_type: str) -> Path:
    """Build the processed PDF path for one raw PDF and form type."""
    relative_path = raw_relative_path(raw_pdf_path)
    output_dir = config.FORM_INPUT_DIRS[form_type] / relative_path.parent
    output_name = f"{config.FORM_OUTPUT_PREFIXES[form_type]}{relative_path.name}"
    return output_dir / output_name


def source_relative_path_from_processed(processed_pdf_path: Path, form_type: str) -> Path:
    """Convert a processed PDF path back to its raw relative PDF path."""
    relative_path = Path(processed_pdf_path).relative_to(config.FORM_INPUT_DIRS[form_type])
    prefix = config.FORM_OUTPUT_PREFIXES[form_type]
    filename = relative_path.name
    if filename.startswith(prefix):
        filename = filename[len(prefix) :]
    return relative_path.with_name(filename)


def source_key_from_processed(processed_pdf_path: Path, form_type: str) -> str:
    """Return a stable slash-separated source key from a processed PDF path."""
    return source_relative_path_from_processed(processed_pdf_path, form_type).as_posix()


def _strip_source_number_prefix(stem: str) -> str:
    """Remove a leading numeric document code from a source filename stem."""
    return re.sub(config.SOURCE_FILENAME_PREFIX_PATTERN, "", stem).strip()


def _safe_output_name_part(value: str) -> str:
    """Sanitize one filename part while preserving Thai text."""
    cleaned = re.sub(config.OUTPUT_FILENAME_INVALID_CHARS_PATTERN, "_", value)
    cleaned = re.sub(r"\s+", "", cleaned).strip("._ ")
    return cleaned or config.UNKNOWN_DISTRICT_NAME


def source_location_parts(source_file: str) -> tuple[str, str]:
    """Extract subdistrict and district names from a source key."""
    source_path = PurePosixPath(source_file.replace("\\", "/"))
    subdistrict = _strip_source_number_prefix(source_path.stem)
    if source_path.parent == PurePosixPath("."):
        district = config.UNKNOWN_DISTRICT_NAME
    else:
        district = source_path.parent.parts[-1]
    return _safe_output_name_part(subdistrict), _safe_output_name_part(district)


def json_output_path(form_type: str, source_file: str) -> Path:
    """Build the per-source JSON output path for one form type."""
    subdistrict, district = source_location_parts(source_file)
    prefix = config.FORM_JSON_PREFIXES[form_type]
    return config.OUTPUT_DIR / f"{prefix}_{subdistrict}_{district}.json"


def json_output_glob(form_type: str) -> str:
    """Return the per-source JSON glob pattern for one form type."""
    return f"{config.FORM_JSON_PREFIXES[form_type]}_*.json"
