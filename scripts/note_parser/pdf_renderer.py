"""
pdf_renderer.py – renders a single PDF page to a PNG base64 data URL.

Uses PyMuPDF (import fitz).  No permanent files are created; the PNG
bytes live only in memory.
"""

from __future__ import annotations

import base64
import io
from typing import Tuple

try:
    import pymupdf as fitz  # PyMuPDF >= 1.24 (preferred import name)
except ImportError:
    import fitz  # type: ignore[no-redef]  # older / fallback

from .config import PDF_RENDER_SCALE


def render_page_to_png_bytes(doc: fitz.Document, page_index: int, scale: float = PDF_RENDER_SCALE) -> bytes:
    """
    Render a single page of an already-open fitz.Document to PNG bytes.

    Parameters
    ----------
    doc         : An open fitz.Document.
    page_index  : 0-based page index.
    scale       : Zoom/scale factor.  2.5 gives ~180 DPI for a typical A4 page,
                  which is sufficient for small mathematical notation.

    Returns
    -------
    PNG bytes (in-memory, no file written).
    """
    page: fitz.Page = doc[page_index]

    # Build a transformation matrix that scales the page.
    mat = fitz.Matrix(scale, scale)

    # Render to a Pixmap (RGBA→RGB; alpha channel not needed).
    pix: fitz.Pixmap = page.get_pixmap(matrix=mat, alpha=False)

    # Return raw PNG bytes.
    return pix.tobytes("png")


def png_bytes_to_data_url(png_bytes: bytes) -> str:
    """Encode PNG bytes as a base64 data URL ready for an image_url content item."""
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def render_page_as_data_url(
    doc: fitz.Document,
    page_index: int,
    scale: float = PDF_RENDER_SCALE,
) -> Tuple[bytes, str]:
    """
    Convenience wrapper that renders a page and returns both the raw PNG bytes
    and the ready-to-use base64 data URL.

    Returns
    -------
    (png_bytes, data_url)
    """
    png_bytes = render_page_to_png_bytes(doc, page_index, scale)
    data_url = png_bytes_to_data_url(png_bytes)
    return png_bytes, data_url
