from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader


DOCX = Path(
    r"C:\Users\joaop\Downloads\14.GRR4C_AI1.13_DC-MSS-IMT_vs_EESS_2200-2290MHz_Compatibility_update.docx"
)
PDF = Path(
    r"C:\GitHub\SHARC\.docx_review_grr4c\14.GRR4C_AI1.13_DC-MSS-IMT_vs_EESS_2200-2290MHz_Compatibility_update.pdf"
)
OUT = Path(r"C:\GitHub\SHARC\.docx_review_grr4c")


def clean(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def iter_blocks(document: Document):
    paragraph_number = 0
    table_number = 0
    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            paragraph_number += 1
            yield "paragraph", paragraph_number, Paragraph(child, document)
        elif child.tag.endswith("}tbl"):
            table_number += 1
            yield "table", table_number, Table(child, document)


def main() -> None:
    document = Document(DOCX)
    blocks: list[dict] = []
    for kind, number, block in iter_blocks(document):
        if kind == "paragraph":
            text = clean(block.text)
            if text:
                blocks.append(
                    {
                        "kind": kind,
                        "number": number,
                        "style": block.style.name if block.style else None,
                        "text": text,
                    }
                )
        else:
            rows = []
            for row in block.rows:
                rows.append([clean(cell.text) for cell in row.cells])
            blocks.append(
                {
                    "kind": kind,
                    "number": number,
                    "rows": rows,
                }
            )

    page_texts = []
    reader = PdfReader(PDF)
    for page_number, page in enumerate(reader.pages, start=1):
        page_texts.append(
            {
                "page": page_number,
                "text": page.extract_text(extraction_mode="layout") or "",
            }
        )

    (OUT / "structure.json").write_text(
        json.dumps(blocks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT / "pages.json").write_text(
        json.dumps(page_texts, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for block in blocks:
        if block["kind"] == "paragraph":
            print(
                f"P{block['number']:03d} [{block['style']}]: {block['text']}"
            )
        else:
            print(f"\n=== TABLE {block['number']} ===")
            for row_number, row in enumerate(block["rows"], start=1):
                print(f"R{row_number:02d}: " + " || ".join(row))
            print("=== END TABLE ===\n")


if __name__ == "__main__":
    main()
