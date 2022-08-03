from __future__ import annotations

from dataclasses import dataclass
from typing import List, Callable, Union, Tuple

from pdfscraper.layout.drawing import (
    Shape,
    process_pymupdf_drawing,
    process_pdfminer_drawing,
)
from pdfscraper.layout.image import Image, get_images_from_pymupdf_page, get_image
from pdfscraper.layout.text import Word, TextLine, Block, Line, Span
from pdfscraper.layout.utils import (
    Bbox,
    group_objs_y,
    get_topmost,
    Orientation,
    create_bbox_backend,
    Backend,
)
from pdfscraper.layout.utils import PageOrientation


class Page:
    def __init__(
        self,
        words: List[Word],
        drawings: List[Shape],
        images: List[Image],
        raw_object: Union["fitz.fitz.Page", "pdfminer.layout.LTPage"],
        blocks: List[Block],
    ) -> None:
        self.words = words
        self.drawings = drawings
        self.images = images
        self.raw_object = raw_object
        self.blocks = blocks
        # self.wordlines = self.sorted

    def __repr__(self) -> str:
        return "Page: %s" % "".join([repr(i) + "\n" for i in self.words])

    def select(self, condition: Callable) -> Page:
        """
        Find content matching condition.
        """
        words = [i for i in self.words if condition(i)]
        drawings = [i for i in self.drawings if condition(i)]
        images = [i for i in self.images if condition(i)]
        ret = Page(words=words, drawings=drawings, images=images, blocks=self.blocks, raw_object=self.raw_object,)
        return ret

    def __add__(self, other) -> 'Page':
        return Page(
            words=self.words + other.words,
            drawings=self.drawings + other.drawings,
            images=self.images + other.images,
            blocks=self.blocks + other.blocks,
            raw_object=[self.raw_object, other.raw_object],
        )

    @staticmethod
    def _split_sequence_by_condition(seq, condition):
        success = []
        failure = []
        for i in seq:
            if condition(i):
                success.append(i)
            else:
                failure.append(i)
        return success, failure

    def split(self, condition: Callable):
        words_true, words_false = self._split_sequence_by_condition(self.words, condition)
        drawings_true, drawings_false = self._split_sequence_by_condition(self.drawings, condition)
        images_true, images_false = self._split_sequence_by_condition(self.images, condition)
        ret_1 = PageSection(
            words=words_true, drawings=drawings_true, images=images_true, parent=self, condition=condition,
        )
        ret_2 = PageSection(
            words=words_false, drawings=drawings_false, images=images_false, parent=self, condition=condition,
        )

        return ret_1, ret_2

    def take_screenshot(self, area: Tuple[float, float, float, float], output_path):
        import fitz

        if isinstance(self.raw_object, fitz.fitz.Page):
            self.raw_object.get_pixmap(dpi=300, clip=area).save(output_path)
        else:
            raise NotImplementedError("Only PyMuPDF pages support taking screenshots.")

    @property
    def sorted(self) -> List[TextLine]:
        if len(self.words) == 0:
            return [[]]
        return [TextLine(line) for line in group_objs_y(self.words)]

    @classmethod
    def from_pymupdf(cls, page: "fitz.fitz.Page", orientation: Orientation = None) -> Page:

        if not orientation:
            page_orientation = PageOrientation.create(
                bottom_is_zero=False, left_is_zero=True, page_width=page.rect.width, page_height=page.rect.height,
            )
        else:
            page_orientation = PageOrientation(
                orientation=orientation, page_width=page.rect.width, page_height=page.rect.height,
            )

        def _get_words_blocks_from_page(page, page_orientation: PageOrientation):
            blocks = page.get_text("rawdict", flags=3)["blocks"]
            for block in blocks:
                for line in block["lines"]:
                    for j, span in enumerate(line["spans"]):
                        line["spans"][j] = Span.from_pymupdf(span, page_orientation)
            for block in blocks:
                for k, line in enumerate(block["lines"]):
                    block["lines"][k] = Line(
                        bbox=create_bbox_backend(
                            backend=Backend.PYMUPDF, coords=line["bbox"], page_orientation=page_orientation,
                        ),
                        spans=line["spans"],
                    )

            for n, block in enumerate(blocks):
                blocks[n] = Block(
                    bbox=create_bbox_backend(
                        backend=Backend.PYMUPDF, coords=block["bbox"], page_orientation=page_orientation,
                    ),
                    lines=block["lines"],
                )
            words = [word for block in blocks for line in block.lines for span in line.spans for word in span.words]

            return words, blocks

        def _get_drawings_from_pymupdf_page(page, page_orientation):
            drawings = sorted(page.get_drawings(), key=lambda x: x["rect"][1])
            drawings = [process_pymupdf_drawing(i, page_orientation) for i in drawings]
            drawings = sorted(drawings, key=get_topmost)
            return drawings

        drawings = _get_drawings_from_pymupdf_page(page, page_orientation)
        words, blocks = _get_words_blocks_from_page(page, page_orientation)  # type: ignore
        pymupdf_images = get_images_from_pymupdf_page(page)
        images = [
            Image.from_pymupdf(image=image, doc=page.parent, page_orientation=page_orientation)
            for image in pymupdf_images
        ]
        page = cls(words=words, drawings=drawings, images=images, raw_object=page, blocks=blocks,)

        return page

    @classmethod
    def from_pdfminer(cls, page: "pdfminer.layout.LTPage", orientation: Orientation = None) -> Page:
        import pdfminer

        if not orientation:
            page_orientation = PageOrientation.create(
                bottom_is_zero=False, left_is_zero=True, page_width=page.width, page_height=page.height,
            )
        else:
            page_orientation = PageOrientation(orientation=orientation, page_width=page.width, page_height=page.height)

        def _get_words_blocks_from_page(page, page_orientation):
            blocks = []
            text_boxes = [i for i in page if hasattr(i, "get_text")]
            for text_box in text_boxes:
                # get text lines
                lines = [text_line for text_line in text_box if hasattr(text_line, "get_text")]
                # convert lines into spans
                lines = [
                    Span.from_pdfminer([i for i in line if type(i) != pdfminer.layout.LTAnno], page_orientation,)
                    for line in lines
                ]
                # make a block out of spans
                blocks.append(Block(bbox=Bbox(*text_box.bbox), lines=lines))
            words = [word for block in blocks for line in block.lines for word in line.words]
            return words, blocks

        def _get_drawings_from_page(page, page_orientation):
            drawings = [i for i in page if issubclass(type(i), pdfminer.layout.LTCurve)]
            drawings = [process_pdfminer_drawing(i, page_orientation) for i in drawings]
            drawings = sorted(drawings, key=get_topmost)
            return drawings

        def _get_images_from_page(page, page_orientation):
            images = filter(bool, map(get_image, page))
            images = [Image.from_pdfminer(image, page_orientation) for image in images]
            return images

        drawings = _get_drawings_from_page(page, page_orientation=page_orientation)
        images = _get_images_from_page(page, page_orientation=page_orientation)
        words, blocks = _get_words_blocks_from_page(page, page_orientation=page_orientation)
        page = cls(words=words, images=images, drawings=drawings, raw_object=page, blocks=blocks,)
        return page


@dataclass
class PageSection(Page):
    words: List[Word]
    drawings: List
    images: List
    condition: str
    parent: Page
    name: str = ""
