import io
import fitz  # PyMuPDF
import docx
import openpyxl

def extract_text_from_pdf(content: bytes) -> str:
    """Extract text from PDF bytes."""
    with fitz.open(stream=content, filetype="pdf") as doc:
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
    return text

def extract_text_from_docx(content: bytes) -> str:
    """Extract text from DOCX bytes."""
    doc = docx.Document(io.BytesIO(content))
    text = []
    for para in doc.paragraphs:
        text.append(para.text)
    # Basic table extraction
    for table in doc.tables:
        for row in table.rows:
            row_text = [cell.text for cell in row.cells]
            text.append(" | ".join(row_text))
            
    return "\n".join(text)

def extract_text_from_xlsx(content: bytes) -> str:
    """Extract text from XLSX bytes (all sheets)."""
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    text = []
    for sheet in wb.sheetnames:
        ws = wb[sheet]
        text.append(f"--- Sheet: {sheet} ---")
        for row in ws.iter_rows(values_only=True):
            row_text = [str(cell) for cell in row if cell is not None]
            if row_text:
                text.append("\t".join(row_text))
    return "\n".join(text)

def extract_text(filename: str, content: bytes) -> str:
    """Dispatcher for text extraction."""
    filename = filename.lower()
    if filename.endswith(".pdf"):
        return extract_text_from_pdf(content)
    elif filename.endswith(".docx"):
        return extract_text_from_docx(content)
    elif filename.endswith(".xlsx"):
        return extract_text_from_xlsx(content)
    else:
        # Fallback: try to decode as text
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return ""
