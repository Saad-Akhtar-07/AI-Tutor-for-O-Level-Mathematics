"""
schemas.py – Pydantic models for the structured extraction output.

Every model-generated page response is validated against these schemas
before being accepted into the final document JSON.

Discriminated unions are used where practical so that Pydantic can
identify the correct block/inline type from the "type" field alone.
"""

from __future__ import annotations

from typing import Annotated, List, Literal, Optional, Union
from pydantic import BaseModel, Field


# ── Inline node types ─────────────────────────────────────────────────────────


class TextInline(BaseModel):
    """Plain text run inside a paragraph, heading or list item."""

    type: Literal["text"]
    text: str


class MathInline(BaseModel):
    """Inline LaTeX expression (KaTeX-compatible)."""

    type: Literal["math"]
    latex: str


# Discriminated union – used inside paragraph / heading / list item content.
InlineNode = Annotated[
    Union[TextInline, MathInline],
    Field(discriminator="type"),
]


# ── Block types ───────────────────────────────────────────────────────────────


class HeadingBlock(BaseModel):
    type: Literal["heading"]
    level: int = Field(ge=1, le=6)
    content: List[InlineNode]


class ParagraphBlock(BaseModel):
    type: Literal["paragraph"]
    content: List[InlineNode]


class MathBlock(BaseModel):
    """Stand-alone (display) LaTeX equation."""

    type: Literal["math"]
    latex: str
    display: bool = True
    needs_review: bool = False


class ListItem(BaseModel):
    """A single item in a bullet or numbered list.

    The content uses the same inline-node system as paragraphs so that
    mathematics inside list items is preserved correctly.

    children contains nested sub-items (e.g. an indented list under a
    parent bullet).  It is optional so that flat lists remain simple.
    """

    content: List[InlineNode]
    children: List["ListItem"] = Field(default_factory=list)


class BulletListBlock(BaseModel):
    type: Literal["bullet_list"]
    items: List[ListItem]


class NumberedListBlock(BaseModel):
    type: Literal["numbered_list"]
    items: List[ListItem]


# ── Table ─────────────────────────────────────────────────────────────────────

# Forward reference – resolved at end of file.
Block = None  # placeholder; real type defined below


class TableCell(BaseModel):
    """A single table cell.  Cells can contain multiple blocks."""

    blocks: List["AnyBlock"]


class TableRow(BaseModel):
    is_header: bool = False
    cells: List[TableCell]


class TableBlock(BaseModel):
    type: Literal["table"]
    rows: List[TableRow]


# ── Figure / diagram ──────────────────────────────────────────────────────────


class FigureBlock(BaseModel):
    type: Literal["figure"]
    figure_type: str  # e.g. "diagram", "graph", "image"
    description: str
    caption: Optional[str] = None
    needs_asset_extraction: bool = True


# ── Discriminated union of all block types ────────────────────────────────────

AnyBlock = Annotated[
    Union[
        HeadingBlock,
        ParagraphBlock,
        MathBlock,
        BulletListBlock,
        NumberedListBlock,
        TableBlock,
        FigureBlock,
    ],
    Field(discriminator="type"),
]

# Resolve forward references now that AnyBlock is defined.
ListItem.model_rebuild()        # children: List["ListItem"]
TableCell.model_rebuild()
TableRow.model_rebuild()
TableBlock.model_rebuild()


# ── Page / document models ────────────────────────────────────────────────────


class PageResult(BaseModel):
    """Validated output for a single PDF page."""

    page_number: int = Field(ge=1)
    blocks: List[AnyBlock]


class DocumentResult(BaseModel):
    """The final JSON file written to parsed_notes/."""

    schema_version: str
    source_pdf: str
    relative_source_path: str
    document_title: str
    subject: str = "Mathematics"
    total_pages: int
    processing_status: Literal["in_progress", "completed", "partial", "failed"]
    failed_pages: List[int] = Field(default_factory=list)
    pages: List[PageResult]
