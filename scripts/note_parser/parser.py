"""
parser.py – core PDF-processing logic.

Responsibilities:
  • find_pdfs()             – discover all PDFs under Notes_data
  • load_existing_progress() – read a partially-complete JSON file
  • save_document_atomic()   – write JSON safely (temp file → rename)
  • parse_model_response()   – clean and parse raw API response text
  • validate_page()          – Pydantic validation for a single page
  • process_pdf()            – process one PDF end-to-end
  • process_all_pdfs()       – orchestrate the full run
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    import pymupdf as fitz  # PyMuPDF >= 1.24
except ImportError:
    import fitz  # type: ignore[no-redef]
from pydantic import ValidationError

from .config import (
    MAX_RETRIES,
    NOTES_DATA_DIR,
    OPENROUTER_MODEL,
    PARSED_NOTES_DIR,
    RETRY_BASE_SECONDS,
    SCHEMA_VERSION,
)
from .openrouter_client import OpenRouterError, call_vision_model
from .pdf_renderer import render_page_as_data_url
from .prompts import PAGE_EXTRACTION_PROMPT, build_user_message_content
from .schemas import DocumentResult, PageResult


# ── PDF discovery ─────────────────────────────────────────────────────────────


def find_pdfs(root: Path = NOTES_DATA_DIR) -> List[Path]:
    """
    Recursively discover all PDF files under *root*.

    Returns a sorted list of absolute Path objects.
    Source files are never modified.
    """
    pdfs = sorted(root.rglob("*.pdf"))
    return pdfs


# ── Output path helpers ───────────────────────────────────────────────────────


def output_path_for_pdf(pdf_path: Path, input_root: Path = NOTES_DATA_DIR, output_root: Path = PARSED_NOTES_DIR) -> Path:
    """
    Mirror the input directory hierarchy inside *output_root*.

    Example:
        Notes_data/Algebra and graphs/2-AlgebraicRoots&Indices.pdf
        →  parsed_notes/Algebra and graphs/2-AlgebraicRoots&Indices.json
    """
    relative = pdf_path.relative_to(input_root)
    json_relative = relative.with_suffix(".json")
    return output_root / json_relative


# ── Document title derivation ─────────────────────────────────────────────────


def _derive_title(pdf_path: Path) -> str:
    """
    Best-effort human-readable title from the PDF filename.

    Example: "2-AlgebraicRoots&Indices.pdf" → "AlgebraicRoots&Indices"
    We strip a leading numeric prefix like "2-" if present.
    """
    stem = pdf_path.stem  # without extension
    # Remove leading digits-and-dash prefix (e.g. "12-")
    title = re.sub(r"^\d+-", "", stem)
    return title


# ── Progress persistence ──────────────────────────────────────────────────────


def load_existing_progress(json_path: Path) -> Tuple[Optional[Dict], Set[int]]:
    """
    Load an existing (possibly partial) output JSON file.

    Returns
    -------
    (raw_dict_or_None, set_of_already_processed_page_numbers)

    Page numbers in the set are 1-based.
    """
    if not json_path.exists():
        return None, set()

    try:
        with json_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        print(f"  [warn] Could not read existing progress file: {json_path}")
        return None, set()

    pages: List[Dict] = data.get("pages", [])
    done: Set[int] = set()
    for page in pages:
        pn = page.get("page_number")
        if isinstance(pn, int):
            done.add(pn)

    return data, done


def save_document_atomic(doc_dict: Dict, json_path: Path) -> None:
    """
    Write *doc_dict* to *json_path* atomically using a temp file + rename.

    This ensures that an interrupted write never leaves a corrupted file.
    """
    json_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to a sibling temp file first.
    tmp_fd, tmp_name = tempfile.mkstemp(
        dir=json_path.parent, prefix=".tmp_", suffix=".json"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            json.dump(doc_dict, fh, ensure_ascii=False, indent=2)
        # Atomic rename (on the same filesystem this is rename(2)).
        os.replace(tmp_name, json_path)
    except Exception:
        # Clean up temp file if something goes wrong.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


# ── Model response parsing ────────────────────────────────────────────────────

# Pattern to strip optional ```json … ``` or ``` … ``` fences.
_FENCE_RE = re.compile(
    r"^```(?:json)?\s*\n?(.*?)\n?```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def parse_model_response(raw: Optional[str]) -> Dict:
    """
    Parse the raw text returned by the model into a Python dict.

    Steps:
      1. Verify raw is a non-empty string.
      2. Strip leading/trailing whitespace.
      3. Remove Markdown code fences if present (safe cleanup only).
      4. json.loads().

    Raises
    ------
    ValueError  – if JSON parsing fails after cleanup or raw is null/empty.
    """
    if not raw or not isinstance(raw, str):
        raise ValueError(f"Model returned empty or non-string response: {raw!r}")

    text = raw.strip()

    # Remove optional Markdown fence.
    m = _FENCE_RE.match(text)
    if m:
        text = m.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON parse error: {exc}\nRaw text (first 500 chars):\n{raw[:500]}") from exc


# ── Pydantic validation ───────────────────────────────────────────────────────


def validate_page(raw_dict: Dict) -> PageResult:
    """
    Validate a parsed dict against the PageResult schema.

    Raises
    ------
    ValidationError  – propagated from Pydantic if the dict is invalid.
    """
    return PageResult.model_validate(raw_dict)


# ── Markdown cleanup ──────────────────────────────────────────────────────────

# Matches **text**, __text__, *text*, _text_ (non-greedy)
# and `inline code`.
_MD_BOLD_RE   = re.compile(r"\*{2}(.+?)\*{2}|_{2}(.+?)_{2}", re.DOTALL)
_MD_ITALIC_RE = re.compile(r"\*(.+?)\*|_(.+?)_", re.DOTALL)
_MD_CODE_RE   = re.compile(r"`(.+?)`", re.DOTALL)


def _clean_text(value: str) -> str:
    """Strip Markdown inline formatting from a plain-text string."""
    # Bold must be handled before italic (** before *).
    value = _MD_BOLD_RE.sub(lambda m: m.group(1) or m.group(2), value)
    value = _MD_ITALIC_RE.sub(lambda m: m.group(1) or m.group(2), value)
    value = _MD_CODE_RE.sub(r"\1", value)
    return value


def _strip_markdown_from_node(node: object) -> None:
    """
    Recursively walk a parsed JSON structure (dicts and lists) and
    strip Markdown formatting from every string stored in a "text" key.

    Only "text" keys are touched; "latex" keys are intentionally left alone.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "text" and isinstance(value, str):
                node[key] = _clean_text(value)  # type: ignore[index]
            else:
                _strip_markdown_from_node(value)
    elif isinstance(node, list):
        for item in node:
            _strip_markdown_from_node(item)


def strip_markdown_from_page(page_dict: Dict) -> Dict:
    """
    Apply _strip_markdown_from_node() to a page dict in-place and return it.

    Called after json.loads() but before Pydantic validation so that
    the cleaned dict is what gets validated and stored.
    """
    _strip_markdown_from_node(page_dict)
    return page_dict


# ── Single page extraction (with per-page retry) ──────────────────────────────


def extract_page(
    doc: fitz.Document,
    page_index: int,
    page_number: int,  # 1-based
    total_pages: int,
    pdf_label: str,
) -> Optional[PageResult]:
    """
    Render one page, call the vision model, validate, and return a PageResult.

    Returns None if all retries are exhausted (caller records failure).
    """
    prefix = f"  Page {page_number}/{total_pages}"

    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        # ── 1. Render page ────────────────────────────────────────────────────
        try:
            print(f"{prefix}: rendering…")
            _, data_url = render_page_as_data_url(doc, page_index)
        except Exception as exc:
            print(f"{prefix}: render failed – {exc}")
            return None  # Render errors are not retryable via API.

        # ── 2. Call API ───────────────────────────────────────────────────────
        try:
            print(f"{prefix}: sending to {OPENROUTER_MODEL}…")
            user_content = build_user_message_content(page_number, data_url)
            raw_response = call_vision_model(
                system_prompt=PAGE_EXTRACTION_PROMPT,
                user_content=user_content,
                page_number=page_number,
            )
        except OpenRouterError as exc:
            print(f"{prefix}: API error – {exc}")
            return None  # Already retried inside call_vision_model.

        # ── 3. Parse JSON ─────────────────────────────────────────────────────
        try:
            parsed_dict = parse_model_response(raw_response)
        except (ValueError, TypeError, AttributeError) as exc:
            last_error = exc
            wait = RETRY_BASE_SECONDS * (2 ** (attempt - 1))
            print(f"{prefix}: attempt {attempt} – invalid response ({exc}).  Retrying in {wait:.0f}s…")
            time.sleep(wait)
            continue

        # ── 3b. Strip any Markdown that leaked into text nodes ────────────────
        strip_markdown_from_page(parsed_dict)

        # ── 4. Pydantic validation ────────────────────────────────────────────
        try:
            page_result = validate_page(parsed_dict)
            # Ensure the model returned the correct page number.
            if page_result.page_number != page_number:
                print(
                    f"{prefix}: [warn] model returned page_number="
                    f"{page_result.page_number}, expected {page_number}. Correcting."
                )
                # Override with the ground-truth page number.
                page_result = PageResult(
                    page_number=page_number, blocks=page_result.blocks
                )
            print(f"{prefix}: valid JSON ✓")
            return page_result

        except ValidationError as exc:
            last_error = exc
            wait = RETRY_BASE_SECONDS * (2 ** (attempt - 1))
            print(
                f"{prefix}: attempt {attempt} – validation error.  "
                f"Retrying in {wait:.0f}s…\n  Detail: {exc}"
            )
            time.sleep(wait)
            continue

    print(f"{prefix}: all {MAX_RETRIES} attempts failed.  Last error: {last_error}")
    return None


# ── Single PDF processing ─────────────────────────────────────────────────────


def process_pdf(
    pdf_path: Path,
    input_root: Path = NOTES_DATA_DIR,
    output_root: Path = PARSED_NOTES_DIR,
    force: bool = False,
) -> Tuple[int, int]:
    """
    Process a single PDF: render each page, extract, validate, save.

    Returns
    -------
    (pages_succeeded, pages_failed)
    """
    relative_str = str(pdf_path.relative_to(input_root))
    json_path = output_path_for_pdf(pdf_path, input_root, output_root)
    title = _derive_title(pdf_path)

    # ── Load existing progress ─────────────────────────────────────────────────
    existing_data, done_pages = load_existing_progress(json_path)

    if force:
        done_pages = set()
        existing_data = None
        if json_path.exists():
            print(f"  [--force] Ignoring existing output: {json_path}")

    # Open the PDF.
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        print(f"  [error] Cannot open PDF: {exc}")
        return 0, 0

    total_pages = doc.page_count

    # Rebuild pages list: keep already-done pages from disk, process the rest.
    pages_dict: Dict[int, Dict] = {}  # page_number → raw dict

    if existing_data and not force:
        for page_dict in existing_data.get("pages", []):
            pn = page_dict.get("page_number")
            if isinstance(pn, int):
                pages_dict[pn] = page_dict

    succeeded = len(pages_dict)
    failed_pages: List[int] = []

    for page_index in range(total_pages):
        page_number = page_index + 1  # 1-based

        if page_number in done_pages and not force:
            print(f"  Page {page_number}/{total_pages}: already extracted, skipping.")
            continue

        result = extract_page(doc, page_index, page_number, total_pages, relative_str)

        if result is not None:
            pages_dict[page_number] = result.model_dump()
            succeeded += 1
        else:
            failed_pages.append(page_number)

        # ── Save progress after each page (atomic) ────────────────────────────
        ordered_pages = [pages_dict[k] for k in sorted(pages_dict)]

        if failed_pages:
            status = "partial"
        elif succeeded < total_pages:
            status = "in_progress"
        else:
            status = "completed"

        doc_dict = {
            "schema_version": SCHEMA_VERSION,
            "source_pdf": pdf_path.name,
            "relative_source_path": relative_str,
            "document_title": title,
            "subject": "Mathematics",
            "total_pages": total_pages,
            "processing_status": status,
            "failed_pages": failed_pages,
            "pages": ordered_pages,
        }

        save_document_atomic(doc_dict, json_path)

    doc.close()

    # ── Final status ──────────────────────────────────────────────────────────
    total_processed = succeeded + len(failed_pages)
    if total_processed == 0:
        # Everything was already done (resume run, nothing new).
        pass
    elif failed_pages:
        ordered_pages = [pages_dict[k] for k in sorted(pages_dict)]
        final_doc_dict = {
            "schema_version": SCHEMA_VERSION,
            "source_pdf": pdf_path.name,
            "relative_source_path": relative_str,
            "document_title": title,
            "subject": "Mathematics",
            "total_pages": total_pages,
            "processing_status": "partial",
            "failed_pages": failed_pages,
            "pages": ordered_pages,
        }
        save_document_atomic(final_doc_dict, json_path)
        print(
            f"\nSaved (partial – failed pages {failed_pages}):\n  {json_path}\n"
        )
    else:
        ordered_pages = [pages_dict[k] for k in sorted(pages_dict)]
        final_doc_dict = {
            "schema_version": SCHEMA_VERSION,
            "source_pdf": pdf_path.name,
            "relative_source_path": relative_str,
            "document_title": title,
            "subject": "Mathematics",
            "total_pages": total_pages,
            "processing_status": "completed",
            "failed_pages": [],
            "pages": ordered_pages,
        }
        save_document_atomic(final_doc_dict, json_path)
        print(f"\nSaved:\n  {json_path}\n")

    return succeeded, len(failed_pages)


# ── Full dataset processing ────────────────────────────────────────────────────


def process_all_pdfs(
    input_root: Path = NOTES_DATA_DIR,
    output_root: Path = PARSED_NOTES_DIR,
    force: bool = False,
    limit: Optional[int] = None,
) -> None:
    """
    Discover and sequentially process all PDFs under *input_root*.

    Parameters
    ----------
    force  : If True, re-process even pages that already have output.
    limit  : If set, process at most this many PDFs (for quick testing).
    """
    pdfs = find_pdfs(input_root)

    if not pdfs:
        print("No PDF files found under:", input_root)
        return

    if limit is not None:
        pdfs = pdfs[:limit]

    total_pdfs = len(pdfs)
    print(f"Found {total_pdfs} PDF(s).\n")

    total_succeeded = 0
    total_failed = 0
    completed_pdfs = 0
    partial_pdfs = 0
    failed_pdfs = 0

    for idx, pdf_path in enumerate(pdfs, start=1):
        relative = pdf_path.relative_to(input_root)
        print(f"[{idx}/{total_pdfs}] {relative}")

        ok, fail = process_pdf(pdf_path, input_root, output_root, force=force)

        total_succeeded += ok
        total_failed += fail

        if fail == 0:
            completed_pdfs += 1
        elif ok == 0:
            failed_pdfs += 1
        else:
            partial_pdfs += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    print("=" * 60)
    print("Processing complete\n")
    print(f"  PDFs discovered : {total_pdfs}")
    print(f"  Completed       : {completed_pdfs}")
    print(f"  Partial         : {partial_pdfs}")
    print(f"  Failed          : {failed_pdfs}")
    print()
    print(f"  Pages succeeded : {total_succeeded}")
    print(f"  Pages failed    : {total_failed}")
    print("=" * 60)
