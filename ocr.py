"""Run Typhoon OCR on split election PDFs."""

from __future__ import annotations

import base64
import asyncio
import copy
import html
import io
import json
import logging
import math
import re
import tempfile
import time
from pathlib import Path
from typing import Any

import fitz
import pandas as pd
import PyPDF2
import requests
from PIL import Image
from tqdm import tqdm

import config
from paths import json_output_path, source_key_from_processed


def _ensure_output_dir() -> None:
    """Create the configured output directory if needed."""
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_api_key() -> None:
    """Raise a clear error when the Typhoon API key is missing."""
    if (
        not config.TYPHOON_API_KEY
        or config.TYPHOON_API_KEY == config.API_KEY_PLACEHOLDER
    ):
        raise ValueError(
            "Typhoon API key is not configured. Set TYPHOON_API_KEY in .env."
        )


def _ensure_llama_parse_api_key() -> None:
    """Raise a clear error when the LlamaParse API key is missing."""
    if not config.LLAMA_CLOUD_API_KEY:
        raise ValueError(
            "LlamaParse API key is not configured. Set LLAMA_CLOUD_API_KEY in .env."
        )


def _ensure_ocr_provider() -> None:
    """Validate provider selection and its required credentials."""
    if config.OCR_PROVIDER not in config.OCR_PROVIDERS:
        raise ValueError(
            f"Unsupported OCR_PROVIDER={config.OCR_PROVIDER!r}. "
            f"Use one of: {', '.join(config.OCR_PROVIDERS)}"
        )
    if config.OCR_PROVIDER == config.OCR_PROVIDER_LLAMAPARSE:
        _ensure_llama_parse_api_key()
    else:
        _ensure_api_key()


def pdf_page_to_base64(pdf_path: Path, page_num: int, dpi: int = config.DPI) -> str:
    """Render one PDF page as a base64-encoded JPEG image."""
    pdf_path = Path(pdf_path)
    with fitz.open(pdf_path) as document:
        page = document.load_page(page_num)
        zoom = dpi / 72
        pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        image = Image.frombytes(
            "RGB",
            (pixmap.width, pixmap.height),
            pixmap.samples,
        )

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=config.JPEG_QUALITY, optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def get_pages_for_unit(pdf_path: Path, unit_index: int, pages_per_unit: int) -> list[int]:
    """Calculate page indexes for a unit in a split PDF."""
    _ = Path(pdf_path)
    start_page = unit_index * pages_per_unit
    return [start_page + offset for offset in range(pages_per_unit)]


def build_user_prompt(form_type: str, names_list: list[str]) -> str:
    """Build the OCR prompt for one form type."""
    entity_label = config.FORM_ENTITY_LABELS[form_type]
    score_entries = ",\n".join(
        f'    "{name}": <int|null>' for name in names_list
    )
    return config.USER_PROMPT_TEMPLATE.format(
        entity_label=entity_label,
        score_entries=score_entries,
    )


def pdf_pages_to_pdf_bytes(pdf_path: Path, page_indexes: list[int]) -> bytes:
    """Create an in-memory PDF containing selected 0-indexed pages."""
    writer = PyPDF2.PdfWriter()
    with Path(pdf_path).open("rb") as input_file:
        reader = PyPDF2.PdfReader(input_file)
        for page_index in page_indexes:
            writer.add_page(reader.pages[page_index])

        output_buffer = io.BytesIO()
        writer.write(output_buffer)
        return output_buffer.getvalue()


def _ocr_payload(page_count: int) -> dict[str, str]:
    """Build form data for the Typhoon OCR endpoint."""
    payload = {
        "model": config.TYPHOON_MODEL,
        "max_tokens": str(config.TYPHOON_MAX_TOKENS),
        "temperature": str(config.TYPHOON_TEMPERATURE),
        "top_p": str(config.TYPHOON_TOP_P),
        "repetition_penalty": str(config.TYPHOON_REPETITION_PENALTY),
        "pages": json.dumps(list(range(1, page_count + 1))),
    }
    if config.TYPHOON_TASK_TYPE:
        payload["task_type"] = config.TYPHOON_TASK_TYPE
    return payload


def _content_to_text(content: str) -> str:
    """Extract readable text from OCR content that may be JSON-wrapped."""
    try:
        parsed_content = json.loads(content)
    except json.JSONDecodeError:
        return content

    if isinstance(parsed_content, dict):
        natural_text = parsed_content.get("natural_text")
        if isinstance(natural_text, str):
            return natural_text
    return content


def extract_text_from_ocr_response(response_json: dict[str, Any]) -> str:
    """Extract successful page text from Typhoon OCR API response JSON."""
    extracted_texts: list[str] = []
    errors: list[str] = []

    for page_result in response_json.get("results", []):
        if page_result.get("success") and page_result.get("message"):
            choices = page_result["message"].get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                if content:
                    extracted_texts.append(_content_to_text(content))
        elif not page_result.get("success"):
            filename = page_result.get("filename", "unknown")
            error = page_result.get("error", "Unknown OCR error")
            errors.append(f"{filename}: {error}")

    if extracted_texts:
        return "\n".join(extracted_texts)
    if errors:
        raise RuntimeError(config.CSV_JOIN_SEPARATOR.join(errors))
    raise RuntimeError("Typhoon OCR returned no text")


def call_typhoon_ocr(pdf_path: Path, page_indexes: list[int]) -> str:
    """Call the Typhoon OCR endpoint with selected pages as one PDF."""
    _ensure_api_key()
    pdf_path = Path(pdf_path)
    unit_pdf_bytes = pdf_pages_to_pdf_bytes(pdf_path, page_indexes)
    files = {
        "file": (
            f"{pdf_path.stem}_pages_{'-'.join(str(index + 1) for index in page_indexes)}.pdf",
            unit_pdf_bytes,
            "application/pdf",
        )
    }
    headers = {"Authorization": f"Bearer {config.TYPHOON_API_KEY}"}

    last_error: Exception | None = None
    for attempt_index in range(config.MAX_RETRIES):
        try:
            response = requests.post(
                config.TYPHOON_OCR_URL,
                files=files,
                data=_ocr_payload(len(page_indexes)),
                headers=headers,
                timeout=120,
            )
            response.raise_for_status()
            return extract_text_from_ocr_response(response.json())
        except Exception as error:
            last_error = error
            if attempt_index >= config.MAX_RETRIES - 1:
                break
            sleep_seconds = config.RETRY_BACKOFF_BASE_SECONDS * (2**attempt_index)
            logging.getLogger(__name__).warning(
                "Typhoon OCR call failed on attempt %s/%s: %s. Retrying in %ss.",
                attempt_index + 1,
                config.MAX_RETRIES,
                error,
                sleep_seconds,
            )
            time.sleep(sleep_seconds)

    raise RuntimeError("Typhoon OCR call failed after retries") from last_error


def _load_llama_cloud_client_class() -> Any:
    """Load the AsyncLlamaCloud client from the installed SDK."""
    try:
        from llama_cloud import AsyncLlamaCloud

        return AsyncLlamaCloud
    except ImportError as error:
        raise ImportError(
            "llama-cloud package is not installed. Run "
            "`pip install -r requirements.txt` first."
        ) from error


def _load_llama_parse_config_file() -> dict[str, Any]:
    """Load optional LlamaParse JSON config exported from the web UI."""
    config_path = Path(config.LLAMA_PARSE_CONFIG_FILE)
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as config_file:
        loaded_config = json.load(config_file)
    if not isinstance(loaded_config, dict):
        raise ValueError(f"LlamaParse config must be a JSON object: {config_path}")
    return loaded_config


def _csv_to_list(value: str) -> list[str]:
    """Convert a comma-separated environment value into a string list."""
    return [item.strip() for item in value.split(",") if item.strip()]


def _llama_parse_request_config() -> dict[str, Any]:
    """Build Llama Cloud parse request settings."""
    file_config = _load_llama_parse_config_file()
    expand = file_config.get("expand") or _csv_to_list(config.LLAMA_PARSE_EXPAND)
    if isinstance(expand, str):
        expand = _csv_to_list(expand)
    return {
        "tier": config.LLAMA_PARSE_TIER or file_config.get("tier", "cost_effective"),
        "version": config.LLAMA_PARSE_VERSION or file_config.get("version", "latest"),
        "expand": expand,
    }


def _llama_result_to_text(result: Any) -> str:
    """Extract full markdown/text content from a Llama Cloud parse result."""
    parts: list[str] = []
    for attribute_name in ("markdown_full", "text_full"):
        value = getattr(result, attribute_name, None)
        if isinstance(value, str) and value.strip():
            parts.append(value)

    if not parts:
        for attribute_name in ("markdown", "text"):
            value = getattr(result, attribute_name, None)
            if isinstance(value, str) and value.strip():
                parts.append(value)
            elif isinstance(value, list):
                parts.extend(str(item) for item in value if str(item).strip())

    return "\n".join(parts).strip()


async def _call_llama_cloud_parse_async(pdf_path: Path, page_indexes: list[int]) -> str:
    """Parse selected PDF pages with Llama Cloud's async API."""
    _ensure_llama_parse_api_key()
    AsyncLlamaCloud = _load_llama_cloud_client_class()
    request_config = _llama_parse_request_config()
    unit_pdf_bytes = pdf_pages_to_pdf_bytes(pdf_path, page_indexes)
    temp_path: Path | None = None

    with tempfile.NamedTemporaryFile(
        suffix=".pdf",
        prefix="election_unit_",
        delete=False,
    ) as temp_file:
        temp_file.write(unit_pdf_bytes)
        temp_path = Path(temp_file.name)

    try:
        async with AsyncLlamaCloud(api_key=config.LLAMA_CLOUD_API_KEY) as client:
            with temp_path.open("rb") as input_file:
                file_obj = await client.files.create(file=input_file, purpose="parse")
            result = await client.parsing.parse(
                file_id=file_obj.id,
                tier=request_config["tier"],
                version=request_config["version"],
                expand=request_config["expand"],
                polling_interval=config.LLAMA_PARSE_POLLING_INTERVAL,
                timeout=config.LLAMA_PARSE_TIMEOUT,
                verbose=config.LLAMA_PARSE_VERBOSE,
            )
        parsed_text = _llama_result_to_text(result)
        if not parsed_text:
            raise RuntimeError("Llama Cloud returned no markdown_full/text_full content")
        return parsed_text
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def call_llama_parse(pdf_path: Path, page_indexes: list[int]) -> str:
    """Parse selected PDF pages with Llama Cloud and return markdown/text."""
    last_error: Exception | None = None
    for attempt_index in range(config.MAX_RETRIES):
        try:
            return asyncio.run(_call_llama_cloud_parse_async(Path(pdf_path), page_indexes))
        except Exception as error:
            last_error = error
            if attempt_index >= config.MAX_RETRIES - 1:
                break
            sleep_seconds = config.RETRY_BACKOFF_BASE_SECONDS * (2**attempt_index)
            logging.getLogger(__name__).warning(
                "Llama Cloud parse call failed on attempt %s/%s: %s. Retrying in %ss.",
                attempt_index + 1,
                config.MAX_RETRIES,
                error,
                sleep_seconds,
            )
            time.sleep(sleep_seconds)

    raise RuntimeError("Llama Cloud parse call failed after retries") from last_error


def call_ocr_provider(pdf_path: Path, page_indexes: list[int]) -> str:
    """Call the configured OCR provider."""
    if config.OCR_PROVIDER == config.OCR_PROVIDER_LLAMAPARSE:
        return call_llama_parse(pdf_path, page_indexes)
    return call_typhoon_ocr(pdf_path, page_indexes)


def parse_json_response(raw_text: str) -> dict[str, Any]:
    """Extract and parse a JSON object from a model response."""
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        return {config.FIELD_PARSE_ERROR: "No JSON object found in response"}

    json_text = match.group(0)
    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as error:
        return {config.FIELD_PARSE_ERROR: f"JSON parse failed: {error}"}

    if not isinstance(parsed, dict):
        return {config.FIELD_PARSE_ERROR: "Parsed JSON is not an object"}
    return parsed


def _number_tokens(text: str) -> list[str]:
    """Extract raw number-like tokens from OCR text."""
    return [
        token.strip()
        for token in re.findall(config.NUMBER_TOKEN_PATTERN, text)
        if token.strip() and token.strip() not in config.DASH_VALUES
    ]


def _token_to_int(token: str) -> int | None:
    """Convert a raw OCR number token into an integer if possible."""
    cleaned = token.translate(config.THAI_DIGIT_TRANSLATION)
    for source, replacement in config.OCR_CONFUSION_MAP.items():
        cleaned = cleaned.replace(source, replacement)
    cleaned = re.sub(r"[,\s]", "", cleaned)
    if cleaned.isdigit():
        return int(cleaned)
    return None


def _html_cell_text(cell_html: str) -> str:
    """Convert one HTML table cell into plain text."""
    with_breaks = re.sub(r"<br\s*/?>", " ", cell_html, flags=re.IGNORECASE)
    without_tags = re.sub(r"<[^>]+>", " ", with_breaks)
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()


def _html_table_rows(raw_text: str) -> list[list[str]]:
    """Extract plain-text cell rows from OCR HTML tables."""
    rows: list[list[str]] = []
    row_matches = re.findall(r"<tr[^>]*>(.*?)</tr>", raw_text, flags=re.DOTALL | re.IGNORECASE)
    for row_html in row_matches:
        cells = [
            _html_cell_text(cell_html)
            for cell_html in re.findall(
                r"<t[dh][^>]*>(.*?)</t[dh]>",
                row_html,
                flags=re.DOTALL | re.IGNORECASE,
            )
        ]
        if cells:
            rows.append(cells)
    return rows


def _extract_scores_from_html_table(
    raw_text: str,
    names_list: list[str],
) -> dict[str, str | None]:
    """Map table row numbers to configured candidate or party names."""
    score_by_number: dict[int, str] = {}
    for cells in _html_table_rows(raw_text):
        if len(cells) < 4:
            continue
        row_number_tokens = _number_tokens(cells[0])
        if not row_number_tokens:
            continue
        row_number = _token_to_int(row_number_tokens[0])
        if row_number is None or row_number <= 0:
            continue

        score_tokens: list[str] = []
        for score_cell in cells[2:]:
            numeric_tokens = [
                token
                for token in _number_tokens(score_cell)
                if _token_to_int(token) is not None
            ]
            if numeric_tokens:
                score_tokens = numeric_tokens
                break
        if not score_tokens:
            continue
        score_by_number[row_number] = score_tokens[0]

    return {
        name: score_by_number.get(index)
        for index, name in enumerate(names_list, start=1)
    }


def _extract_value_near_alias(lines: list[str], aliases: list[str]) -> str | None:
    """Find the nearest number token on or just after a labelled line."""
    for line_index, line in enumerate(lines):
        compact_line = re.sub(r"\s+", "", line)
        for alias in aliases:
            compact_alias = re.sub(r"\s+", "", alias)
            if compact_alias not in compact_line:
                continue
            current_tokens = _number_tokens(line)
            if current_tokens:
                return current_tokens[-1]
            for next_line in lines[line_index + 1 : line_index + 3]:
                next_tokens = _number_tokens(next_line)
                if next_tokens:
                    return next_tokens[-1]
    return None


def _extract_score_for_name(lines: list[str], name: str) -> str | None:
    """Find a score value on the row containing a candidate or party name."""
    compact_name = re.sub(r"\s+", "", name)
    for line_index, line in enumerate(lines):
        compact_line = re.sub(r"\s+", "", line)
        if name not in line and compact_name not in compact_line:
            continue
        current_tokens = _number_tokens(line)
        if current_tokens:
            return current_tokens[-1]
        if line_index + 1 < len(lines):
            next_tokens = _number_tokens(lines[line_index + 1])
            if next_tokens:
                return next_tokens[-1]
    return None


def parse_election_text(raw_text: str, names_list: list[str]) -> dict[str, Any]:
    """Parse election fields from Typhoon OCR text."""
    parsed_json = parse_json_response(raw_text)
    if not parsed_json.get(config.FIELD_PARSE_ERROR):
        return parsed_json

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    table_scores = _extract_scores_from_html_table(raw_text, names_list)
    if not any(value is not None for value in table_scores.values()):
        table_scores = {
            name: _extract_score_for_name(lines, name) for name in names_list
        }

    parsed = {
        config.FIELD_BALLOT_TOTAL: _extract_value_near_alias(
            lines,
            config.BALLOT_FIELD_ALIASES[config.FIELD_BALLOT_TOTAL],
        ),
        config.FIELD_BALLOT_VALID: _extract_value_near_alias(
            lines,
            config.BALLOT_FIELD_ALIASES[config.FIELD_BALLOT_VALID],
        ),
        config.FIELD_BALLOT_INVALID: _extract_value_near_alias(
            lines,
            config.BALLOT_FIELD_ALIASES[config.FIELD_BALLOT_INVALID],
        ),
        config.FIELD_BALLOT_NO_VOTE: _extract_value_near_alias(
            lines,
            config.BALLOT_FIELD_ALIASES[config.FIELD_BALLOT_NO_VOTE],
        ),
        config.FIELD_SCORES: table_scores,
    }
    found_values = [
        parsed[config.FIELD_BALLOT_TOTAL],
        parsed[config.FIELD_BALLOT_VALID],
        parsed[config.FIELD_BALLOT_INVALID],
        parsed[config.FIELD_BALLOT_NO_VOTE],
        *parsed[config.FIELD_SCORES].values(),
    ]
    if not any(value is not None for value in found_values):
        parsed[config.FIELD_PARSE_ERROR] = "No structured election values found in OCR text"
    return parsed


def normalize_source_file_name(pdf_path: Path, form_type: str) -> str:
    """Convert a split PDF filename back to the original raw PDF filename."""
    return source_key_from_processed(Path(pdf_path), form_type)


def _page_count(pdf_path: Path) -> int:
    """Count pages in a PDF."""
    with fitz.open(pdf_path) as document:
        return document.page_count


def _empty_scores(names_list: list[str]) -> dict[str, None]:
    """Build a score dictionary with null values."""
    return {name: None for name in names_list}


def ocr_unit(
    pdf_path: Path,
    unit_index: int,
    form_type: str,
    names_list: list[str],
) -> dict[str, Any]:
    """OCR one polling unit and return a normalized result record."""
    pdf_path = Path(pdf_path)
    pages_per_unit = config.FORM_SPLIT_PAGES_PER_UNIT[form_type]
    result: dict[str, Any] = {
        config.FIELD_SOURCE_FILE: normalize_source_file_name(pdf_path, form_type),
        config.FIELD_UNIT_INDEX: unit_index,
        config.FIELD_FORM_TYPE: form_type,
        config.FIELD_BALLOT_TOTAL: None,
        config.FIELD_BALLOT_VALID: None,
        config.FIELD_BALLOT_INVALID: None,
        config.FIELD_BALLOT_NO_VOTE: None,
        config.FIELD_SCORES: _empty_scores(names_list),
        config.FIELD_RAW_RESPONSE: "",
        config.FIELD_PARSE_ERROR: None,
    }

    try:
        total_pages = _page_count(pdf_path)
        page_indexes = [
            page_index
            for page_index in get_pages_for_unit(pdf_path, unit_index, pages_per_unit)
            if page_index < total_pages
        ]
        if not page_indexes:
            result[config.FIELD_PARSE_ERROR] = "No pages found for unit"
            return result

        raw_response = call_ocr_provider(pdf_path, page_indexes)
        parsed = parse_election_text(raw_response, names_list)
        result[config.FIELD_RAW_RESPONSE] = raw_response

        if parsed.get(config.FIELD_PARSE_ERROR):
            result[config.FIELD_PARSE_ERROR] = parsed[config.FIELD_PARSE_ERROR]
            return result

        result[config.FIELD_BALLOT_TOTAL] = parsed.get(config.FIELD_BALLOT_TOTAL)
        result[config.FIELD_BALLOT_VALID] = parsed.get(config.FIELD_BALLOT_VALID)
        result[config.FIELD_BALLOT_INVALID] = parsed.get(config.FIELD_BALLOT_INVALID)
        result[config.FIELD_BALLOT_NO_VOTE] = parsed.get(
            config.FIELD_BALLOT_NO_VOTE
        )
        parsed_scores = parsed.get(config.FIELD_SCORES) or {}
        if not isinstance(parsed_scores, dict):
            result[config.FIELD_PARSE_ERROR] = "scores is not an object"
            return result
        result[config.FIELD_SCORES] = {
            name: parsed_scores.get(name) for name in names_list
        }
        return result
    except Exception as error:
        result[config.FIELD_PARSE_ERROR] = str(error)
        return result


def reparse_result_from_raw_response(
    result: dict[str, Any],
    form_type: str,
) -> dict[str, Any]:
    """Refresh structured fields from an existing raw OCR response."""
    updated_result = copy.deepcopy(result)
    raw_response = updated_result.get(config.FIELD_RAW_RESPONSE)
    if not isinstance(raw_response, str) or not raw_response.strip():
        return updated_result

    names_list = config.FORM_NAMES[form_type]
    parsed = parse_election_text(raw_response, names_list)
    for stale_field in (
        config.FIELD_STATUS,
        config.FIELD_CROSS_STATUS,
        config.FIELD_CROSS_ISSUES,
        config.FIELD_STAT_FLAGS,
        config.FIELD_CLEANING_NOTES,
        config.FIELD_ISSUES,
    ):
        updated_result.pop(stale_field, None)

    if parsed.get(config.FIELD_PARSE_ERROR):
        updated_result[config.FIELD_PARSE_ERROR] = parsed[config.FIELD_PARSE_ERROR]
        return updated_result

    updated_result[config.FIELD_PARSE_ERROR] = None
    updated_result[config.FIELD_BALLOT_TOTAL] = parsed.get(config.FIELD_BALLOT_TOTAL)
    updated_result[config.FIELD_BALLOT_VALID] = parsed.get(config.FIELD_BALLOT_VALID)
    updated_result[config.FIELD_BALLOT_INVALID] = parsed.get(config.FIELD_BALLOT_INVALID)
    updated_result[config.FIELD_BALLOT_NO_VOTE] = parsed.get(config.FIELD_BALLOT_NO_VOTE)
    parsed_scores = parsed.get(config.FIELD_SCORES) or {}
    updated_result[config.FIELD_SCORES] = {
        name: parsed_scores.get(name) for name in names_list
    }
    return updated_result


def reparse_results(
    results: list[dict[str, Any]],
    form_type: str,
) -> list[dict[str, Any]]:
    """Refresh structured fields in many OCR results from raw responses."""
    return [
        reparse_result_from_raw_response(result, form_type)
        for result in results
    ]


def _join_csv_value(value: Any) -> str:
    """Format list-like values for CSV output."""
    if value is None:
        return ""
    if isinstance(value, list):
        return config.CSV_JOIN_SEPARATOR.join(str(item) for item in value)
    return str(value)


def _combined_issues(result: dict[str, Any]) -> list[str]:
    """Combine internal and cross-form issues for CSV output."""
    issues: list[str] = []
    for field_name in (config.FIELD_ISSUES, config.FIELD_CROSS_ISSUES):
        value = result.get(field_name) or []
        if isinstance(value, list):
            issues.extend(str(item) for item in value)
        else:
            issues.append(str(value))
    return issues


def save_outputs(results: list[dict[str, Any]], form_type: str) -> None:
    """Save combined CSV and per-source JSON results."""
    _ensure_output_dir()
    names_list = config.FORM_NAMES[form_type]
    output_files = config.OUTPUT_FILES[form_type]
    columns = [*config.BASE_CSV_COLUMNS, *names_list]
    rows: list[dict[str, Any]] = []
    results_by_source: dict[str, list[dict[str, Any]]] = {}

    for result in results:
        source_file = str(result.get(config.FIELD_SOURCE_FILE, "unknown.pdf"))
        results_by_source.setdefault(source_file, []).append(result)
        row: dict[str, Any] = {
            config.FIELD_SOURCE_FILE: source_file,
            config.FIELD_UNIT_INDEX: result.get(config.FIELD_UNIT_INDEX),
            config.FIELD_STATUS: result.get(
                config.FIELD_STATUS,
                config.DEFAULT_PENDING_STATUS,
            ),
            config.FIELD_CROSS_STATUS: result.get(
                config.FIELD_CROSS_STATUS,
                config.DEFAULT_PENDING_STATUS,
            ),
            config.FIELD_STAT_FLAGS: _join_csv_value(
                result.get(config.FIELD_STAT_FLAGS)
            ),
            config.FIELD_BALLOT_TOTAL: result.get(config.FIELD_BALLOT_TOTAL),
            config.FIELD_BALLOT_VALID: result.get(config.FIELD_BALLOT_VALID),
            config.FIELD_BALLOT_INVALID: result.get(config.FIELD_BALLOT_INVALID),
            config.FIELD_BALLOT_NO_VOTE: result.get(config.FIELD_BALLOT_NO_VOTE),
            config.FIELD_CLEANING_NOTES: _join_csv_value(
                result.get(config.FIELD_CLEANING_NOTES)
            ),
            config.FIELD_ISSUES: _join_csv_value(_combined_issues(result)),
        }
        scores = result.get(config.FIELD_SCORES) or {}
        for name in names_list:
            row[name] = scores.get(name)
        rows.append(row)

    dataframe = pd.DataFrame(rows, columns=columns)
    dataframe.to_csv(
        config.OUTPUT_DIR / output_files["csv"],
        index=False,
        encoding="utf-8-sig",
    )

    for source_file, source_results in results_by_source.items():
        with json_output_path(form_type, source_file).open(
            "w",
            encoding="utf-8",
        ) as output_file:
            json.dump(source_results, output_file, ensure_ascii=False, indent=2)


def run_ocr(form_type: str) -> list[dict[str, Any]]:
    """Run OCR for all split PDFs of one form type."""
    if form_type not in config.FORM_TYPES:
        raise ValueError(f"Unsupported form type: {form_type}")
    _ensure_ocr_provider()

    input_dir = config.FORM_INPUT_DIRS[form_type]
    names_list = config.FORM_NAMES[form_type]
    pages_per_unit = config.FORM_SPLIT_PAGES_PER_UNIT[form_type]
    input_dir.mkdir(parents=True, exist_ok=True)
    _ensure_output_dir()

    logger = logging.getLogger(__name__)
    results: list[dict[str, Any]] = []
    pdf_paths = sorted(path for path in input_dir.rglob("*.pdf") if path.is_file())
    logger.info(
        "Starting OCR for %s with provider=%s and %s PDF(s)",
        form_type,
        config.OCR_PROVIDER,
        len(pdf_paths),
    )

    for pdf_path in pdf_paths:
        total_pages = _page_count(pdf_path)
        total_units = math.ceil(total_pages / pages_per_unit)
        progress = tqdm(
            range(total_units),
            desc=f"OCR {form_type} {pdf_path.name}",
            unit="unit",
        )
        for unit_index in progress:
            result = ocr_unit(pdf_path, unit_index, form_type, names_list)
            results.append(result)
            if result.get(config.FIELD_PARSE_ERROR):
                logger.warning(
                    "OCR issue in %s unit %s: %s",
                    pdf_path.name,
                    unit_index,
                    result[config.FIELD_PARSE_ERROR],
                )
            time.sleep(config.SLEEP_BETWEEN_CALLS)

    save_outputs(results, form_type)
    logger.info("Finished OCR for %s: %s records", form_type, len(results))
    return results
