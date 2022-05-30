import os

import fitz
from pdfminer.high_level import extract_pages

from pdfscraper.layout.annotations import PDFMinerAnnotation, PyMuPDFAnnotation, Annotation
from pdfscraper.page import Page
from pdfscraper.layout.utils import PageVerticalOrientation

HERE = os.path.abspath(os.path.dirname(__file__))


def test_drawings():
    test_path = os.path.join(HERE, 'samples', 'test2.pdf')
    doc = fitz.open(test_path)
    fitz_page = doc[0]
    pdfminer_page = list(extract_pages(test_path))[0]
    for mupdf_drawing, pdfminer_drawing in zip(Page.from_mupdf(fitz_page).drawings,
                                               Page.from_pdfminer(pdfminer_page).drawings):
        assert mupdf_drawing.fill_color == pdfminer_drawing.fill_color
        assert mupdf_drawing.stroke_color == pdfminer_drawing.stroke_color
        assert mupdf_drawing.bbox.__eq__(pdfminer_drawing.bbox, n=2)


def test_images():
    test_path = os.path.join(HERE, 'samples', 'test2.pdf')
    doc = fitz.open(test_path)
    fitz_page = doc[0]
    pdfminer_page = list(extract_pages(test_path))[0]
    for mupdf_drawing, pdfminer_drawing in zip(Page.from_mupdf(fitz_page).images,
                                               Page.from_pdfminer(pdfminer_page).images):
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
    test_path = os.path.join(HERE, 'samples', 'test2.pdf')
    doc = fitz.open(test_path)
    fitz_page = doc[0]
    pdfminer_page = list(extract_pages(test_path))[0]
    for mupdf_image, pdfminer_image in zip(Page.from_mupdf(fitz_page).images,
                                           Page.from_pdfminer(pdfminer_page).images):
        mupdf_image.save('test.png')
        pdfminer_image.save('test.png')


def test_text():
    test_path = os.path.join(HERE, 'samples', 'words_test.pdf')
    doc = fitz.open(test_path)
    fitz_page = doc[0]
    pages = extract_pages(test_path)
    pdfminer_page = next(pages)
    for mupdf_line, pdfminer_line in zip(Page.from_mupdf(fitz_page).sorted,
                                         Page.from_pdfminer(pdfminer_page).sorted):
        for mupdf_word, pdfminer_word in zip(mupdf_line, pdfminer_line):
            assert (mupdf_word.text == pdfminer_word.text)


def test_annotations():
    from pdfminer.layout import LAParams
    from pdfminer.converter import PDFResourceManager, PDFPageAggregator
    from pdfminer.pdfpage import PDFPage
    from pdfminer.layout import LTTextBoxHorizontal
    from pdfminer.pdfinterp import PDFPageInterpreter
    from pdfminer import pdftypes

    path = os.path.join(HERE, 'samples', 'anno_test.pdf')
    document = open(path, 'rb')
    rsrcmgr = PDFResourceManager()
    laparams = LAParams()
    # Create a PDF page aggregator object.
    device = PDFPageAggregator(rsrcmgr, laparams=laparams)
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    for page in PDFPage.get_pages(document):
        interpreter.process_page(page)
        # receive the LTPage object for the page.
        layout = device.get_result()
        for element in layout:
            if isinstance(element, LTTextBoxHorizontal):
                print(element.get_text())
        break
    miner_annots = pdftypes.resolve1(page.annots)
    doc = fitz.open(path)
    page = doc[0]
    annots = list(page.annots())

    orientation = PageVerticalOrientation(bottom_is_zero=False, page_height=layout.height)
    for a1, a2 in zip(annots, [i.resolve() for i in miner_annots]):
        anno1 = PyMuPDFAnnotation.from_annot(a1)
        anno2 = PDFMinerAnnotation.from_annot(a2)
        assert (Annotation.from_pymupdf_annot(anno1, orientation=orientation).content ==
                Annotation.from_pdfminer_annot(anno2, orientation=orientation).content)
