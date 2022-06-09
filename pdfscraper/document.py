from dataclasses import dataclass
from typing import List, Any

from pdfscraper.page import Page
from pdfscraper.layout.utils import PageOrientation

@dataclass
class Document:
    pages: List[Page]
    doc: Any
    orientation: PageOrientation

    @classmethod
    def from_mupdf(cls, path, orientation) -> 'Document':
        if isinstance(path, str):
            import fitz
            doc = fitz.open(path)
            return cls(pages=[Page.from_pymupdf(page, orientation=orientation) for page in doc], doc=doc)

    @classmethod
    def from_pdfminer(cls, path, orientation) -> 'Document':
        if isinstance(path, str):
            import pdfminer
            pages = pdfminer.high_level.extract_pages(path)
            return cls([Page.from_pdfminer(page, orientation=orientation) for page in pages], doc=None)

    def create_sections(self):
        pass
