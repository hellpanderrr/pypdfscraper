import fitz
from pdfminer.high_level import extract_pages

from pdfscraper.layout import Page


def test_drawings():
    path = r'samples\test2.pdf'
    doc = fitz.open(path)
    fitz_page = doc[0]
    pdfminer_page = list(extract_pages(path))[0]
    for mupdf_drawing, pdfminer_drawing in zip(Page.from_mupdf(fitz_page).drawings,
                                               Page.from_pdfminer(pdfminer_page).drawings):
        assert mupdf_drawing.fill_color == pdfminer_drawing.fill_color
        assert mupdf_drawing.stroke_color == pdfminer_drawing.stroke_color
        assert mupdf_drawing.bbox.__eq__(pdfminer_drawing.bbox, n=2)
        assert mupdf_drawing.fill == pdfminer_drawing.fill
        assert mupdf_drawing.stroke == pdfminer_drawing.stroke
