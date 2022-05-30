from dataclasses import dataclass
from typing import List, Any

import fitz
import pdfminer

from page import Page


@dataclass
class Document:
    pages: List[Page]
    doc: Any

    @classmethod
    def from_mupdf(cls, path) -> 'Document':
        if isinstance(path, str):
            doc = fitz.open(path)
            return cls(pages=[Page.from_mupdf(page) for page in doc], doc=doc)

    @classmethod
    def from_pdfminer(cls, path) -> 'Document':
        if isinstance(path, str):
            pages = pdfminer.high_level.extract_pages(path)
            return cls([Page.from_pdfminer(page) for page in pages], doc=None)

    def create_sections(self):
        pass