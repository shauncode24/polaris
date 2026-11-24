import asyncio
from io import BytesIO
from typing import BinaryIO

import pdfplumber


class PdfParseError(ValueError):
    """The uploaded bytes started like a PDF but could not be read as one
    (corrupt, truncated or encrypted). Surfaces to the client as a 400.
    """


def extract_text_from_pdf(file: BinaryIO) -> str:
    try:
        text_parts = []
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text(x_tolerance=1, y_tolerance=3)
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception as e:  # pdfplumber/pdfminer raise many unrelated types on bad input
        raise PdfParseError(f"Could not read this PDF: {type(e).__name__}.") from e


async def extract_text_from_pdf_bytes(file_bytes: bytes) -> str:
    """Parses off the event loop: PDF extraction is CPU-bound and would
    otherwise stall every other request while it runs.
    """
    return await asyncio.to_thread(extract_text_from_pdf, BytesIO(file_bytes))
