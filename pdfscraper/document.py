from dataclasses import dataclass
from typing import List, Any

from pdfscraper.layout.utils import Orientation
from pdfscraper.page import Page


@dataclass
class Document:
    pages: List[Page]
    doc: Any
    orientation: Orientation

    @classmethod
    def from_pymupdf(
        cls,
        path,
        orientation: Orientation = Orientation.create(
            bottom_is_zero=False, left_is_zero=True
        ),
    ) -> "Document":

        if isinstance(path, str):
            import fitz

            doc = fitz.open(path)
            return cls(
                pages=[
                    Page.from_pymupdf(page, orientation=orientation) for page in doc
                ],
                doc=doc,
                orientation=orientation,
            )

    @classmethod
    def from_pdfminer(
        cls,
        path,
        orientation: Orientation = Orientation.create(
            bottom_is_zero=False, left_is_zero=True
        ),
    ) -> "Document":

        if isinstance(path, str):
            import pdfminer
            import pdfminer.high_level
            pages = pdfminer.high_level.extract_pages(path)
            return cls(
                [Page.from_pdfminer(page, orientation=orientation) for page in pages],
                doc=None,
                orientation=orientation,
            )

    def create_sections(self):
        pass
