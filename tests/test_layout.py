import os

import fitz
import pdfminer
import pdfminer.high_level
from pdfscraper.layout.annotations import (
    PDFMinerAnnotation,
    PyMuPDFAnnotation,
    Annotation,
)
from pdfscraper.layout.utils import PageOrientation
from pdfscraper.page import Page

HERE = os.path.abspath(os.path.dirname(__file__))


def test_drawings():
    test_path = os.path.join(HERE, "samples", "test2.pdf")
    doc = fitz.open(test_path)
    fitz_page = doc[0]
    pdfminer_page = list(pdfminer.high_level.extract_pages(test_path))[0]
    for mupdf_drawing, pdfminer_drawing in zip(
        Page.from_pymupdf(fitz_page).drawings,
        Page.from_pdfminer(pdfminer_page).drawings,
    ):
        assert mupdf_drawing.fill_color == pdfminer_drawing.fill_color
        assert mupdf_drawing.stroke_color == pdfminer_drawing.stroke_color
        assert mupdf_drawing.bbox.__eq__(pdfminer_drawing.bbox, n=2)


def test_images():
    test_path = os.path.join(HERE, "samples", "test2.pdf")
    doc = fitz.open(test_path)
    fitz_page = doc[0]
    pdfminer_page = list(pdfminer.high_level.extract_pages(test_path))[0]
    for mupdf_drawing, pdfminer_drawing in zip(
        Page.from_pymupdf(fitz_page).images, Page.from_pdfminer(pdfminer_page).images
    ):
        assert mupdf_drawing.bbox == pdfminer_drawing.bbox
        assert mupdf_drawing.bpc == pdfminer_drawing.bpc
        assert mupdf_drawing.colorspace_name == pdfminer_drawing.colorspace_name
        assert mupdf_drawing.name == pdfminer_drawing.name
        assert mupdf_drawing.xref == pdfminer_drawing.xref
        assert mupdf_drawing.source_height == pdfminer_drawing.source_height
        assert mupdf_drawing.source_width == pdfminer_drawing.source_width
        assert round(mupdf_drawing.width) == round(pdfminer_drawing.width)
        assert round(mupdf_drawing.height) == round(pdfminer_drawing.height)


def test_images_saving():
    test_path = os.path.join(HERE, "samples", "test2.pdf")
    doc = fitz.open(test_path)
    fitz_page = doc[0]
    pdfminer_page = list(pdfminer.high_level.extract_pages(test_path))[0]
    for mupdf_image, pdfminer_image in zip(
        Page.from_pymupdf(fitz_page).images, Page.from_pdfminer(pdfminer_page).images
    ):
        mupdf_image.save("test.png")
        pdfminer_image.save("test.png")


def test_text():
    test_path = os.path.join(HERE, "samples", "words_test.pdf")
    doc = fitz.open(test_path)
    fitz_page = doc[0]
    pages = pdfminer.high_level.extract_pages(test_path)
    pdfminer_page = next(pages)
    for mupdf_line, pdfminer_line in zip(
        Page.from_pymupdf(fitz_page).sorted, Page.from_pdfminer(pdfminer_page).sorted
    ):
        for mupdf_word, pdfminer_word in zip(mupdf_line, pdfminer_line):
            assert mupdf_word.text == pdfminer_word.text


def test_annotations():
    from pdfminer.layout import LAParams
    from pdfminer.converter import PDFResourceManager, PDFPageAggregator
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfinterp import PDFPageInterpreter
    from pdfminer import pdftypes

    path = os.path.join(HERE, "samples", "anno_test.pdf")
    document = open(path, "rb")
    rsrcmgr = PDFResourceManager()
    laparams = LAParams()
    # Create a PDF page aggregator object.
    device = PDFPageAggregator(rsrcmgr, laparams=laparams)
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    doc = fitz.open(path)

    for pdfminer_page, mupdf_page in zip(PDFPage.get_pages(document), doc):

        interpreter.process_page(pdfminer_page)
        # receive the LTPage object for the page.
        layout = device.get_result()
        miner_annots = pdftypes.resolve1(pdfminer_page.annots)
        if miner_annots:
            miner_annots = [i.resolve() for i in miner_annots]
            miner_annots = [
                i for i in miner_annots if i.get("Subtype").name != ("Link")
            ]
        else:
            miner_annots = []
        annots = list(mupdf_page.annots())
        if not annots and miner_annots:
            continue
        orientation = PageOrientation.create(
            bottom_is_zero=False,
            left_is_zero=True,
            page_width=layout.width,
            page_height=layout.height,
        )

        for a1, a2 in zip(annots, miner_annots):
            anno1 = PyMuPDFAnnotation.from_annot(a1)
            anno2 = PDFMinerAnnotation.from_annot(a2)

            assert (
                Annotation.from_pymupdf_annot(anno1, orientation=orientation).content
                == Annotation.from_pdfminer_annot(
                    anno2, orientation=orientation
                ).content
            )
