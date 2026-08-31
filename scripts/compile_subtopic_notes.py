#!/usr/bin/env python3
"""
compile_subtopic_notes.py – compile parsed notes JSON files into per-subtopic bundles for the frontend.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARSED_DIR = PROJECT_ROOT / "parsed_notes"
FRONTEND_NOTES_DIR = PROJECT_ROOT / "frontend" / "src" / "data" / "notes"

# Subtopic Mapping configuration
SUBTOPIC_MAPPINGS: List[Dict[str, Any]] = [
    {
        "code": "8.1",
        "topic": "8",
        "title": "Introduction to probability",
        "sources": [
            {
                "file": "Probability/1-ProbabilityToolkit.json",
                "label": "Probability Toolkit",
                "pages": [1, 2, 3, 4, 5],
            }
        ],
    },
    {
        "code": "8.2",
        "topic": "8",
        "title": "Relative and expected frequencies",
        "sources": [
            {
                "file": "Probability/1-ProbabilityToolkit.json",
                "label": "Relative & Expected Frequency",
                "pages": [11, 12, 13],
            }
        ],
    },
    {
        "code": "8.3",
        "topic": "8",
        "title": "Probability of combined events",
        "sources": [
            {
                "file": "Probability/1-ProbabilityToolkit.json",
                "label": "Possibility & Sample Space Diagrams",
                "pages": [6, 7, 8, 9, 10],
            },
            {
                "file": "Probability/2-ProbabilityDiagrams (Tree&Venn.json",
                "label": "Probability Diagrams (Two-Way Tables, Venn & Tree Diagrams)",
                "pages": list(range(1, 15)),
            },
        ],
    },
]


def load_parsed_json(rel_path: str) -> Dict[str, Any]:
    file_path = PARSED_DIR / rel_path
    if not file_path.exists():
        raise FileNotFoundError(f"Parsed note file not found: {file_path}")
    return json.loads(file_path.read_text(encoding="utf-8"))


def build_subtopic_payload(mapping: Dict[str, Any]) -> Dict[str, Any]:
    code = mapping["code"]
    title = mapping["title"]
    topic = mapping["topic"]
    
    sections = []
    
    for src in mapping["sources"]:
        data = load_parsed_json(src["file"])
        target_pages = set(src["pages"])
        
        extracted_pages = []
        for p in data.get("pages", []):
            if p.get("page_number") in target_pages:
                extracted_pages.append(p)
                
        sections.append({
            "source_file": src["file"],
            "source_label": src["label"],
            "document_title": data.get("document_title", ""),
            "pages": extracted_pages,
        })
        
    return {
        "subtopic_code": code,
        "subtopic_title": title,
        "topic_number": topic,
        "sections": sections,
    }


def main():
    FRONTEND_NOTES_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {}

    for mapping in SUBTOPIC_MAPPINGS:
        code = mapping["code"]
        payload = build_subtopic_payload(mapping)
        out_file = FRONTEND_NOTES_DIR / f"{code}.json"
        out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        
        total_pages = sum(len(s["pages"]) for s in payload["sections"])
        total_blocks = sum(sum(len(p.get("blocks", [])) for p in s["pages"]) for s in payload["sections"])
        manifest[code] = {
            "title": mapping["title"],
            "topic": mapping["topic"],
            "total_pages": total_pages,
            "total_blocks": total_blocks,
            "file": f"{code}.json",
        }
        print(f"[OK] Generated {code}.json: {total_pages} pages, {total_blocks} blocks")

    manifest_file = FRONTEND_NOTES_DIR / "manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Wrote manifest.json")

    # Generate index.js for clean ES module imports
    index_code = """// Auto-generated subtopic notes loader
"""
    for code in manifest.keys():
        var_name = "notes_" + code.replace(".", "_")
        index_code += f"import {var_name} from './{code}.json'\n"

    index_code += "\nexport const subtopicNotes = {\n"
    for code in manifest.keys():
        var_name = "notes_" + code.replace(".", "_")
        index_code += f"  '{code}': {var_name},\n"
    index_code += "}\n\n"

    index_code += """export function getNotesForSubtopic(code) {
  return subtopicNotes[code] || null
}
"""
    index_file = FRONTEND_NOTES_DIR / "index.js"
    index_file.write_text(index_code, encoding="utf-8")
    print(f"[OK] Wrote index.js")


if __name__ == "__main__":
    main()
