from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup
from docx import Document as DocxDocument
from pypdf import PdfReader


@dataclass(frozen=True)
class Block:
    text: str
    page: int | None = None
    heading_path: tuple[str, ...] = ()
    is_table: bool = False


def parse_file(path: Path) -> list[Block]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return [
            Block(text=(page.extract_text() or "").strip(), page=index)
            for index, page in enumerate(PdfReader(str(path)).pages, 1)
            if (page.extract_text() or "").strip()
        ]
    if suffix == ".docx":
        doc = DocxDocument(str(path))
        blocks: list[Block] = []
        docx_headings: list[str] = []
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue
            style = paragraph.style.name if paragraph.style else ""
            if style.lower().startswith("heading"):
                level = int(style.split()[-1]) if style.split()[-1].isdigit() else 1
                docx_headings = docx_headings[: max(0, level - 1)] + [text]
            else:
                blocks.append(Block(text, heading_path=tuple(docx_headings)))
        for table in doc.tables:
            rows = [
                [cell.text.replace("\n", " ").strip() for cell in row.cells] for row in table.rows
            ]
            if rows:
                width = max(map(len, rows))
                header = rows[0] + [""] * (width - len(rows[0]))
                body = rows[1:]
                markdown = "| " + " | ".join(header) + " |\n| " + " | ".join(["---"] * width) + " |"
                markdown += "".join(
                    "\n| " + " | ".join(row + [""] * (width - len(row))) + " |" for row in body
                )
                blocks.append(Block(markdown, heading_path=tuple(docx_headings), is_table=True))
        return blocks
    raw = path.read_text(encoding="utf-8", errors="replace")
    if suffix in {".html", ".htm"}:
        soup = BeautifulSoup(raw, "html.parser")
        blocks = []
        html_headings: list[str] = []
        for element in (
            soup.body.find_all(["h1", "h2", "h3", "h4", "p", "li", "table"]) if soup.body else []
        ):
            text = element.get_text(" ", strip=True)
            if not text:
                continue
            if element.name and element.name.startswith("h"):
                level = int(element.name[1])
                html_headings = html_headings[: level - 1] + [text]
            else:
                blocks.append(
                    Block(text, heading_path=tuple(html_headings), is_table=element.name == "table")
                )
        return blocks
    if suffix in {".md", ".markdown"}:
        blocks = []
        markdown_headings: list[str] = []
        paragraph_lines: list[str] = []
        for line in raw.splitlines():
            if line.lstrip().startswith("#"):
                if paragraph_lines:
                    blocks.append(
                        Block("\n".join(paragraph_lines), heading_path=tuple(markdown_headings))
                    )
                    paragraph_lines = []
                title = line.lstrip().lstrip("#").strip()
                level = len(line.lstrip()) - len(line.lstrip().lstrip("#"))
                markdown_headings = markdown_headings[: level - 1] + [title]
            elif not line.strip():
                if paragraph_lines:
                    blocks.append(
                        Block(
                            "\n".join(paragraph_lines),
                            heading_path=tuple(markdown_headings),
                            is_table=any("|" in x for x in paragraph_lines),
                        )
                    )
                    paragraph_lines = []
            else:
                paragraph_lines.append(line)
        if paragraph_lines:
            blocks.append(
                Block(
                    "\n".join(paragraph_lines),
                    heading_path=tuple(markdown_headings),
                    is_table=any("|" in x for x in paragraph_lines),
                )
            )
        return blocks
    return [Block(part.strip()) for part in raw.split("\n\n") if part.strip()]
