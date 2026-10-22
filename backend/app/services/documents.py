"""Source documents: PDF text extraction, chunking and embeddings. Also a tiny PDF writer for seed documents."""

import io
import re
import textwrap

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.ai.embeddings import embed
from app.models.kb import DocumentChunk, SourceDocument
from app.storage import get_storage

CHUNK_CHARS = 700
CHUNK_OVERLAP = 120


def extract_pages(data: bytes) -> list[str]:
    reader = PdfReader(io.BytesIO(data))
    return [(page.extract_text() or "").strip() for page in reader.pages]


def chunk_text(text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 1 <= size:
            current = f"{current} {para}".strip()
            continue
        if current:
            chunks.append(current)
            current = current[-overlap:] + " " + para if overlap else para
        else:
            current = para
        while len(current) > size:
            chunks.append(current[:size])
            current = current[size - overlap :]
    if current.strip():
        chunks.append(current.strip())
    return chunks


def index_document(db: Session, doc: SourceDocument, pages: list[str]) -> int:
    for chunk in list(doc.chunks):
        db.delete(chunk)
    db.flush()
    ordinal = 0
    for page_no, page_text in enumerate(pages, start=1):
        for piece in chunk_text(page_text):
            db.add(DocumentChunk(document_id=doc.id, client_id=doc.client_id, ord=ordinal, page=page_no, text=piece, embedding=embed(f"{doc.title}. {piece}")))
            ordinal += 1
    doc.pages = len(pages)
    doc.status = "procesado" if ordinal else "sin_texto"
    db.flush()
    return ordinal


def process_document(db: Session, doc: SourceDocument) -> int:
    if not doc.file_key:
        return 0
    try:
        pages = extract_pages(get_storage().read(doc.file_key))
    except Exception as exc:  # noqa: BLE001
        doc.status, doc.error = "error", str(exc)[:500]
        return 0
    return index_document(db, doc, pages)


# ----------------------------------------------------------------- minimal PDF writer (seed / tests)


def _pdf_escape(line: str) -> bytes:
    raw = line.encode("cp1252", errors="replace")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def make_text_pdf(title: str, paragraphs: list[str]) -> bytes:
    """Write a simple multi-page A4 PDF with real (extractable) text in Helvetica."""
    lines: list[tuple[str, int]] = [(title, 14), ("", 11)]
    for para in paragraphs:
        for wrapped in textwrap.wrap(para, 88) or [""]:
            lines.append((wrapped, 11))
        lines.append(("", 11))
    per_page = 50
    pages = [lines[i : i + per_page] for i in range(0, len(lines), per_page)] or [[("", 11)]]

    objects: list[bytes] = []
    font_obj = 3
    page_objs = []
    content_start = 4 + len(pages)
    for i in range(len(pages)):
        page_objs.append(4 + i)
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{n} 0 R" for n in page_objs).encode()
    objects.append(b"<< /Type /Pages /Kids [" + kids + b"] /Count " + str(len(pages)).encode() + b" >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    for i in range(len(pages)):
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 {font_obj} 0 R >> >> /Contents {content_start + i} 0 R >>".encode()
        )
    for page in pages:
        stream = b"BT 50 800 Td 15 TL "
        for text, size in page:
            stream += f"/F1 {size} Tf ".encode() + b"(" + _pdf_escape(text) + b") ' "
        stream += b"ET"
        objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for num, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{num} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()
