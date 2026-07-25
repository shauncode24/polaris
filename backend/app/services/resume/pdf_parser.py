import pdfplumber


def extract_text_from_pdf(file_bytes: bytes) -> str:
    text_parts = []
    with pdfplumber.open(file_bytes) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text(x_tolerance=1, y_tolerance=3)
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)