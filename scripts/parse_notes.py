#!/usr/bin/env python3
"""
parse_notes.py – entry-point for the PDF → structured JSON pipeline.

Usage
-----
  # Process all PDFs (resume-aware):
  python scripts/parse_notes.py

  # Process a single PDF:
  python scripts/parse_notes.py --pdf "Notes_data/Algebra and graphs/2-AlgebraicRoots&Indices.pdf"

  # Force re-extraction even if output already exists:
  python scripts/parse_notes.py --force

  # Limit to the first N PDFs (useful for quick smoke-tests):
  python scripts/parse_notes.py --limit 1

Flags may be combined:
  python scripts/parse_notes.py --pdf "Notes_data/..." --force
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add the scripts/ directory to sys.path so that `note_parser` is importable
# whether this file is run directly or as a module.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from note_parser.config import NOTES_DATA_DIR, OPENROUTER_API_KEY, OPENROUTER_MODEL, PARSED_NOTES_DIR
from note_parser.parser import find_pdfs, process_all_pdfs, process_pdf


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="parse_notes.py",
        description="Convert mathematics revision-note PDFs to structured JSON via Ox Alpha.",
    )
    parser.add_argument(
        "--pdf",
        metavar="PATH",
        help="Process only this single PDF (path relative to project root or absolute).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-process pages even if output JSON already exists.",
    )
    parser.add_argument(
        "--limit",
        metavar="N",
        type=int,
        default=None,
        help="Process at most N PDFs (ignored when --pdf is given).",
    )
    parser.add_argument(
        "--input",
        metavar="DIR",
        default=str(NOTES_DATA_DIR),
        help=f"Root directory containing source PDFs (default: {NOTES_DATA_DIR}).",
    )
    parser.add_argument(
        "--output",
        metavar="DIR",
        default=str(PARSED_NOTES_DIR),
        help=f"Root directory for JSON output (default: {PARSED_NOTES_DIR}).",
    )
    return parser


def main() -> int:
    arg_parser = _build_arg_parser()
    args = arg_parser.parse_args()

    input_root = Path(args.input)
    output_root = Path(args.output)

    # ── Preflight checks ──────────────────────────────────────────────────────
    if not OPENROUTER_API_KEY:
        print(
            "[error] OPENROUTER_API_KEY is not set.\n"
            "  Create a .env file in the project root with:\n"
            "    OPENROUTER_API_KEY=your_key_here\n"
            "  Or export the variable in your shell."
        )
        return 1

    # Never print the actual key – just confirm it was loaded.
    masked = OPENROUTER_API_KEY[:8] + "..." if len(OPENROUTER_API_KEY) > 8 else "***"
    print(f"OpenRouter key   : {masked}")
    print(f"Model            : {OPENROUTER_MODEL}")
    print(f"Input directory  : {input_root}")
    print(f"Output directory : {output_root}")
    print()

    if not input_root.exists():
        print(f"[error] Input directory does not exist: {input_root}")
        return 1

    # ── Single-PDF mode ───────────────────────────────────────────────────────
    if args.pdf:
        pdf_path = Path(args.pdf)
        if not pdf_path.is_absolute():
            # Resolve relative to project root (two levels up from scripts/).
            project_root = _SCRIPTS_DIR.parent
            pdf_path = (project_root / pdf_path).resolve()

        if not pdf_path.exists():
            print(f"[error] PDF not found: {pdf_path}")
            return 1

        if not pdf_path.is_file():
            print(f"[error] Path is not a file: {pdf_path}")
            return 1

        # Determine the correct input_root so the output mirror works.
        # The PDF must be inside input_root.
        try:
            pdf_path.relative_to(input_root)
        except ValueError:
            print(
                f"[error] --pdf path ({pdf_path}) is not under --input ({input_root}).\n"
                "  Make sure the PDF is inside the Notes_data directory."
            )
            return 1

        print(f"Single-PDF mode: {pdf_path.relative_to(input_root)}\n")
        ok, fail = process_pdf(pdf_path, input_root, output_root, force=args.force)
        return 0 if fail == 0 else 1

    # ── Full dataset mode ─────────────────────────────────────────────────────
    process_all_pdfs(
        input_root=input_root,
        output_root=output_root,
        force=args.force,
        limit=args.limit,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
