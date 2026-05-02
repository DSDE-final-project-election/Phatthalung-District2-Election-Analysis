"""Split source election PDFs into constituency and party-list PDFs."""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

import PyPDF2

import config


def split_election_pdfs(
    input_pdf_path: Path,
    const_output_path: Path,
    partylist_output_path: Path,
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    """Split one raw PDF into constituency and party-list PDFs."""
    active_logger = logger or logging.getLogger(__name__)
    input_pdf_path = Path(input_pdf_path)
    const_output_path = Path(const_output_path)
    partylist_output_path = Path(partylist_output_path)
    const_output_path.parent.mkdir(parents=True, exist_ok=True)
    partylist_output_path.parent.mkdir(parents=True, exist_ok=True)

    with input_pdf_path.open("rb") as infile:
        reader = PyPDF2.PdfReader(infile)
        total_pages = len(reader.pages)
        total_units = math.ceil(total_pages / config.PAGES_PER_UNIT)
        const_writer = PyPDF2.PdfWriter()
        partylist_writer = PyPDF2.PdfWriter()

        for first_page in range(0, total_pages, config.PAGES_PER_UNIT):
            for offset in config.CONST_PAGE_INDICES:
                page_num = first_page + offset
                if page_num < total_pages:
                    const_writer.add_page(reader.pages[page_num])

            for offset in config.PARTY_PAGE_INDICES:
                page_num = first_page + offset
                if page_num < total_pages:
                    partylist_writer.add_page(reader.pages[page_num])

        with const_output_path.open("wb") as const_file:
            const_writer.write(const_file)
        with partylist_output_path.open("wb") as party_file:
            partylist_writer.write(party_file)

    active_logger.info(
        "Split %s into %s constituency pages and %s party-list pages (%s units)",
        input_pdf_path.name,
        len(const_writer.pages),
        len(partylist_writer.pages),
        total_units,
    )
    return {
        "input_file": input_pdf_path.name,
        "total_pages": total_pages,
        "total_units": total_units,
        "constituency_pages": len(const_writer.pages),
        "partylist_pages": len(partylist_writer.pages),
        "const_output": str(const_output_path),
        "partylist_output": str(partylist_output_path),
    }


def split_all(logger: logging.Logger | None = None) -> dict[str, int]:
    """Split all PDFs in the configured raw directory."""
    active_logger = logger or logging.getLogger(__name__)
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    config.PROCESSED_CONST_DIR.mkdir(parents=True, exist_ok=True)
    config.PROCESSED_PARTY_DIR.mkdir(parents=True, exist_ok=True)

    summary = {"processed": 0, "skipped": 0, "failed": 0, "total": 0}
    pdf_paths = sorted(config.RAW_DIR.glob("*.pdf"))
    active_logger.info("Found %s raw PDF(s) in %s", len(pdf_paths), config.RAW_DIR)

    for input_pdf_path in pdf_paths:
        summary["total"] += 1
        const_output_path = (
            config.PROCESSED_CONST_DIR
            / f"{config.FORM_OUTPUT_PREFIXES[config.FORM_CONSTITUENCY]}{input_pdf_path.name}"
        )
        partylist_output_path = (
            config.PROCESSED_PARTY_DIR
            / f"{config.FORM_OUTPUT_PREFIXES[config.FORM_PARTYLIST]}{input_pdf_path.name}"
        )

        if const_output_path.exists() and partylist_output_path.exists():
            summary["skipped"] += 1
            active_logger.info(
                "Skip %s because split outputs already exist",
                input_pdf_path.name,
            )
            continue

        try:
            split_election_pdfs(
                input_pdf_path,
                const_output_path,
                partylist_output_path,
                active_logger,
            )
            summary["processed"] += 1
        except Exception:
            summary["failed"] += 1
            active_logger.exception("Failed to split %s", input_pdf_path)

    active_logger.info("Split summary: %s", summary)
    return summary
