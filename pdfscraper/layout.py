from __future__ import annotations

import itertools
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal, TypeVar
from typing import Optional
from typing import TypedDict
from typing import Union, List, Callable, Tuple, Dict, Any, NamedTuple

import fitz
import pdfminer
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTRect, LTLine, LTCurve
from pdfminer import pdftypes
import unicodedata
from pydantic import confloat

from pdfscraper.utils import (
    group_objs_y,
    get_leftmost,
    get_rightmost,
    get_topmost,
    get_bottommost,
)

TEST = 5

ImageSource = Literal["pdfminer", "mupdf"]


@dataclass(frozen=True)
class Color:
    r: confloat(ge=0, le=1)
    g: confloat(ge=0, le=1)
    b: confloat(ge=0, le=1)

    def __eq__(self, other, decimals=1):
        if (
                round(self.r, decimals) == round(other.r, decimals)
                and round(self.b, decimals) == round(other.b, decimals)
                and round(self.g, decimals) == round(other.g, decimals)
        ):
            return True
        else:
            return False


@dataclass(frozen=True)
class Point:
    x: float
    y: float


class Bbox(NamedTuple):
    x0: float
    y0: float
    x1: float
    y1: float

    def __str__(self):
        return (
            f"Bbox(x0={self.x0:.2f},y0={self.y0:.2f},x1={self.x1:.2f},y1={self.y1:.2f})"
        )

    def __eq__(self, other, decimals=1, n=4):
        return [round(i, ndigits=decimals) for i in self[:n]] == [
            round(i, ndigits=decimals) for i in other[:n]
        ]

    @property
    def height(self):
        return abs(self.y0 - self.y1)

    @property
    def width(self):
        return abs(self.x0 - self.x1)

    @classmethod
    def from_coords(cls, coords, invert_y=False, page_height=None):
        if invert_y:
            x0, y0, x1, y1 = coords
            y0, y1 = page_height - y1, page_height - y0
            return cls(x0, y0, x1, y1)

    def set_vertical_orientation(self, orientation: PageVerticalOrientation):
        pass


class Word:
    __slots__ = ("text", "bbox", "font", "size", "color")

    def __init__(
            self,
            text: str = "",
            bbox: Union[Bbox, List[int], Tuple[int]] = None,
            font: str = "",
            size: str = "",
            color=None,
            normalize_text=False,
    ):
        self.text = text
        if normalize_text:
            self.text = self.text.replace("\xad", "-")
            self.text = unicodedata.normalize("NFKD", self.text)
        self.bbox = bbox
        self.font = font
        self.size = size
        self.color = color

    def __hash__(self):
        return hash(repr(self))

    def __repr__(self):
        return f'Word(text="{self.text}",bbox={self.bbox})'

    def __eq__(self, other):
        if (self.text, self.bbox) == (other.text, other.bbox):
            return True
        return False

    def __str__(self):
        return self.text


class Span:
    __slots__ = ("words", "bbox")

    def __init__(self, words: List[Word] = None, bbox: Bbox = None):
        """
        A collection of words.
        """
        self.words = words
        self.bbox = bbox

    @property
    def text(self):
        return "".join([i.text for i in self.words])

    def __repr__(self):
        return "Span <%s> %s" % ([round(i) for i in self.bbox], self.words)


class Line:
    __slots__ = ("bbox", "spans")

    def __init__(self, bbox: List[float], spans):
        self.bbox = bbox
        self.spans = spans

    def __repr__(self):
        # '\n'.join([i.text for i in self.spans])
        return "Line: %s" % self.spans

    @property
    def text(self):
        return " ".join([i.text for i in self.spans])


class Block:
    __slots__ = ("bbox", "lines")

    def __init__(self, bbox: Bbox, lines):
        """
        A collection spans.
        """
        self.bbox = bbox
        self.lines = lines

    def __repr__(self):
        return "Block: %s" % self.lines


@dataclass(frozen=True)
class Drawing:
    bbox: Bbox
    fill_color: Optional[Color]
    stroke_color: Optional[Color]
    fill: bool
    stroke: bool


@dataclass(frozen=True)
class RectShape(Drawing):
    points: Optional[Tuple[Point, Point, Point, Point]]


@dataclass(frozen=True)
class LineShape(Drawing):
    points: Optional[Tuple[Point, Point]]


@dataclass(frozen=True)
class CurveShape(Drawing):
    points: Optional[Tuple[Point, Point, Point, Point]]




def get_pts(drawing: Dict) -> List:
    ret = []
    for i in drawing["items"]:
        for j in i[1:]:
            if isinstance(j, fitz.fitz.Rect):
                ret.append(j.bl)
                ret.append(j.br)
            else:
                ret.append(j)
    return ret


Shape = TypeVar('Shape', bound=Union[LineShape, RectShape, CurveShape])


def process_pdfminer_drawing(drawing: Union[LTRect, LTLine, LTCurve], orientation) -> Shape:
    fill = drawing.fill
    fill_color = None
    stroke_color = None
    if fill:
        if hasattr(drawing.non_stroking_color, '__len__'):
            if len(drawing.non_stroking_color) == 1:
                drawing.non_stroking_color *= 3
            fill_color = Color(*drawing.non_stroking_color)
        else:
            if drawing.non_stroking_color:
                fill_color = Color(*[drawing.non_stroking_color]*3)
            else:
                fill_color = Color(0, 0, 0)
    stroke = drawing.stroke
    if stroke:
        if len(drawing.stroking_color) == 1:
            drawing.stroking_color *= 3
        stroke_color = Color(*drawing.stroking_color)
    # pdfminer has bottom as y-zero
    if orientation.bottom_is_zero:
        bbox = Bbox(*drawing.bbox)
    else:
        bbox = Bbox.from_coords(
            coords=drawing.bbox, invert_y=True, page_height=orientation.page_height
        )
    pts = None  # drawing.pts
    args = {
        "fill": fill,
        "fill_color": fill_color,
        "stroke": stroke,
        "stroke_color": stroke_color,
        "bbox": bbox,
        "points": pts,
    }
    if isinstance(drawing, LTRect):
        return RectShape(**args)
    elif isinstance(drawing, LTLine):
        return LineShape(**args)
    elif isinstance(drawing, LTCurve):
        return CurveShape(**args)


def process_mupdf_drawing(drawing: Dict, orientation) -> Shape:
    items = drawing["items"]
    fill = "f" in drawing["type"]
    fill_color = Color(*drawing["fill"]) if fill else None
    stroke = "s" in drawing["type"]
    stroke_color = Color(*drawing["color"]) if stroke else None
    # mupdf has top as y-zero
    if orientation.bottom_is_zero:
        bbox = Bbox.from_coords(
            coords=drawing["rect"], invert_y=True, page_height=orientation.page_height
        )
    else:
        bbox = Bbox(*drawing["rect"])
    pts = None  # get_pts(drawing)
    args = {
        "fill": fill,
        "fill_color": fill_color,
        "stroke": stroke,
        "stroke_color": stroke_color,
        "bbox": bbox,
        "points": pts,
    }

    drawing_commands = [item[0] for item in items]
    if len(drawing_commands) == 1:
        if drawing_commands[0] == "l":
            return LineShape(**args)
        if drawing_commands[0] == "re":
            return RectShape(**args)
        else:
            return CurveShape(**args)
    else:
        return CurveShape(**args)


@dataclass(frozen=True)
class PageVerticalOrientation:
    bottom_is_zero: bool
    page_height: float


@contextmanager
def attr_as(obj, field: str, value) -> None:
    old_value = getattr(obj, field)
    setattr(obj, field, value)
    yield
    setattr(obj, field, old_value)


@dataclass(frozen=True)
class Image:
    bbox: Bbox
    width: float
    height: float
    source_width: float
    source_height: float
    colorspace_name: str
    bpc: int
    xref: int
    name: str
    source: ImageSource
    raw_object: Any = None
    parent_object: Any = None
    colorspace_n: Optional[int] = None

    class Config:
        arbitrary_types_allowed = True

    def _save_pdfminer(self, path: str):
        path, ext = os.path.splitext(path)
        path = os.path.abspath(path)
        folder, name = os.path.split(path)
        im = self.raw_object
        with attr_as(im, "name", name):
            return pdfminer.image.ImageWriter(folder).export_image(im)

    def _save_mupdf(self, path: str):
        with open(path, "wb") as f:
            f.write(self.parent_object.extract_image(self.xref)["image"])

    def save(self, path: str):
        if self.source == "pdfminer":
            self._save_pdfminer(path)
        elif self.source == "mupdf":
            self._save_mupdf(path)

    @classmethod
    def from_pdfminer(
            cls, image: pdfminer.layout.LTImage, orientation: PageVerticalOrientation
    ) -> Image:
        """
        Create an image out of pdfminer object.

        :param image: pdfminer LTImage object.
        :param orientation: page vertical orientation data.
        :return:
        """
        if orientation.bottom_is_zero:
            bbox = Bbox(*image.bbox)
        else:
            bbox = Bbox.from_coords(
                coords=image.bbox, invert_y=True, page_height=orientation.page_height
            )
        bpc = image.bits
        if hasattr(image.colorspace[0], "name"):
            colorspace_name = image.colorspace[0].name
        else:
            objs = image.colorspace[0].resolve()
            if type(objs) == pdfminer.psparser.PSLiteral:
                colorspace_name = objs.name
            else:
                colorspaces = [i for i in objs if hasattr(i, "name")]
                colorspace_name = colorspaces[0].name

        name = image.name
        source_width, source_height = image.srcsize
        width, height = image.width, image.height
        xref = image.stream.objid
        return cls(
            bbox=bbox,
            width=width,
            height=height,
            source_width=source_width,
            source_height=source_height,
            colorspace_name=colorspace_name,
            bpc=bpc,
            xref=xref,
            name=name,
            raw_object=image,
            source="pdfminer",
        )

    @classmethod
    def from_mupdf(
            cls, image: Dict, doc: fitz.fitz.Document, orientation: PageVerticalOrientation
    ) -> Image:
        bbox = image.get("bbox")
        if orientation.bottom_is_zero:
            bbox = Bbox.from_coords(
                coords=bbox, invert_y=True, page_height=orientation.page_height
            )
        else:
            bbox = Bbox(*bbox)
        bpc = image.get("bpc")
        colorspace_name = image.get("colorspace_name")
        name = image.get("name")
        source_width, source_height = (
            image.get("source_width"),
            image.get("source_height"),
        )
        width, height = bbox.width, bbox.height
        xref = image.get("xref")
        return cls(
            bbox=bbox,
            width=width,
            height=height,
            source_width=source_width,
            source_height=source_height,
            colorspace_name=colorspace_name,
            bpc=bpc,
            xref=xref,
            name=name,
            raw_object=image,
            source="mupdf",
            parent_object=doc,
        )


class MuPDFImage(TypedDict):
    xref: int
    mask_xref: int
    source_width: int
    source_height: int
    bpc: int
    colorspace_name: str
    name: str
    decode_filter: str
    bbox: Tuple


def get_images_from_mupdf_page(page) -> MuPDFImage:
    images = page.get_images(full=True)
    for (
            xref,
            smask,
            source_width,
            source_height,
            bpc,
            colorspace,
            alt_colorspace,
            name,
            decode_filter,
            referencer_xref
    ) in images:
        bbox = page.get_image_bbox((
            xref,
            smask,
            source_width,
            source_height,
            bpc,
            colorspace,
            alt_colorspace,
            name,
            decode_filter,
            referencer_xref
        ))
        yield {
            "xref": xref,
            "mask_xref": smask,
            "source_width": source_width,
            "source_height": source_height,
            "bpc": bpc,
            "colorspace_name": colorspace,
            "name": name,
            "decode_filter": decode_filter,
            "bbox": bbox,
        }


def process_span_fitz(span: dict, orientation) -> Span:
    words = [
        list(g)
        for k, g in (
            itertools.groupby(span["chars"], key=lambda x: x["c"] not in (" ", "\xa0"))
        )
    ]
    new_words = []
    coords = []

    for word in words:
        x0, y0 = get_leftmost(word[0]["bbox"]), get_topmost(word[0]["bbox"])
        x1, y1 = get_rightmost(word[-1]["bbox"]), get_bottommost(word[-1]["bbox"])

        coords.append([x0, y0, x1, y1])
        text = "".join([c["c"] for c in word])
        if orientation.bottom_is_zero:
            bbox = Bbox.from_coords((x0, y0, x1, y1), invert_y=True, page_height=orientation.page_height)
        else:
            bbox = Bbox(x0=x0, y0=y0, x1=x1, y1=y1)
        new_words.append(
            Word(
                **{
                    "text": text,
                    "bbox": bbox,
                    "font": span["font"],
                    "size": span["size"],
                    "color": span["color"],
                },
                normalize_text=True,
            )
        )
    bbox = get_span_bbox(new_words)
    ret = Span(words=new_words, bbox=bbox)
    return ret


def process_span_pdfminer(
        span: List[pdfminer.layout.LTChar], orientation
) -> Span:
    """
    Convert a list of pdfminer characters into a Span.

    Split a list by space into Words.

    @param span: list of characters

    """
    words = [
        list(g)
        for k, g in (
            itertools.groupby(span, key=lambda x: x.get_text() not in (" ", "\xa0"))
        )
    ]
    new_words = []
    coords = []

    for word in words:
        if type(word) == pdfminer.layout.LTAnno:
            continue
        # reversing y-coordinates: in pdfminer the zero is the bottom of the page
        # make it top
        x0, y0 = word[0].x0, word[0].y0
        x1, y1 = word[-1].x1, word[-1].y1

        coords.append([x0, y0, x1, y1])
        text = "".join([c.get_text() for c in word])
        font = word[0].fontname
        size = word[0].size
        if not orientation.bottom_is_zero:
            bbox = Bbox.from_coords(coords=(x0, y0, x1, y1), invert_y=True, page_height=orientation.page_height)
        else:
            bbox = Bbox(x0=x0, y0=y0, x1=x1, y1=y1)

        new_words.append(
            Word(
                **{
                    "text": text,
                    "bbox": bbox,
                    "font": font,
                    "size": size,
                    "color": None,
                },
                normalize_text=True,
            )
        )
    bbox = get_span_bbox(new_words)
    ret = Span(words=new_words, bbox=bbox)
    return ret


def get_image(layout_object) -> Optional[pdfminer.layout.LTImage]:
    if isinstance(layout_object, pdfminer.layout.LTImage):
        return layout_object
    if isinstance(layout_object, pdfminer.layout.LTContainer):
        for child in layout_object:
            return get_image(child)
    else:
        return None


class Page:
    def __init__(self, words: List[Word], drawings: List[Shape], images: List[Image],
                 raw_object: Union[fitz.fitz.Page, pdfminer.layout.LTPage], blocks: List[Block]) -> None:
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
        ret = Page(words=words, drawings=drawings, images=images, blocks=self.blocks, raw_object=self.raw_object)
        return ret

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
        ret_1 = PageSection(words=words_true, drawings=drawings_true, images=images_true, parent=self,
                            condition=condition)
        ret_2 = PageSection(words=words_false, drawings=drawings_false, images=images_false, parent=self,
                            condition=condition)

        return ret_1, ret_2

    def take_screenshot(self, area: Tuple[float, float, float, float], output_path):
        if isinstance(self.raw_object, fitz.fitz.Page):
            self.raw_object.get_pixmap(dpi=300, clip=area).save(output_path)
        else:
            raise NotImplementedError('Only PyMuPDF pages support taking screenshots.')

    @property
    def sorted(self) -> List[List[Word]]:
        if len(self.words) == 0:
            return [[]]
        return group_objs_y(self.words)

    @classmethod
    def from_mupdf(cls, page: fitz.fitz.Page) -> Page:
        orientation = PageVerticalOrientation(
            bottom_is_zero=False, page_height=Bbox(*page.rect).height
        )
        def _get_blocks_from_page(page):
            blocks = page.get_text("rawdict", flags=3)["blocks"]
            for block in blocks:
                for line in block["lines"]:
                    for j, span in enumerate(line["spans"]):
                        line["spans"][j] = process_span_fitz(span, orientation)
            for block in blocks:
                for k, line in enumerate(block["lines"]):
                    block["lines"][k] = Line(bbox=(line["bbox"]), spans=line["spans"])

            for n, block in enumerate(blocks):
                blocks[n] = Block(bbox=(block["bbox"]), lines=block["lines"])
            return blocks

        drawings = sorted(page.get_drawings(), key=lambda x: x["rect"][1])
        drawings = [process_mupdf_drawing(i, orientation) for i in drawings]
        drawings = sorted(drawings, key=get_topmost)

        blocks = _get_blocks_from_page(page)
        words = [
            word
            for block in blocks
            for line in block.lines
            for span in line.spans
            for word in span.words
        ]

        images = get_images_from_mupdf_page(page)
        images = [Image.from_mupdf(image, page.parent, orientation) for image in images]

        page = cls(words=words, drawings=drawings, images=images, raw_object=page, blocks=blocks)

        return page

    @classmethod
    def from_pdfminer(cls, page: pdfminer.layout.LTPage) -> Page:
        blocks = []
        text_boxes = [i for i in page if hasattr(i, "get_text")]
        orientation = PageVerticalOrientation(
            bottom_is_zero=False, page_height=page.height
        )
        for text_box in text_boxes:
            # get text lines
            lines = [
                text_line for text_line in text_box if hasattr(text_line, "get_text")
            ]
            # convert lines into spans
            lines = [
                process_span_pdfminer([i for i in line if type(i) != pdfminer.layout.LTAnno], orientation)
                for line in lines
            ]
            # make a block out of spans
            blocks.append(Block(bbox=Bbox(*text_box.bbox), lines=lines))
        words = [
            word for block in blocks for line in block.lines for word in line.words
        ]
        drawings = [i for i in page if issubclass(type(i), pdfminer.layout.LTCurve)]

        drawings = [process_pdfminer_drawing(i, orientation) for i in drawings]
        drawings = sorted(drawings, key=get_topmost)
        images = filter(bool, map(get_image, page))
        images = [Image.from_pdfminer(image, orientation) for image in images]
        page = cls(words=words, images=images, drawings=drawings, raw_object=page, blocks=blocks)
        return page


@dataclass
class PageSection(Page):
    words: List[Word]
    drawings: List
    images: List
    condition: str
    parent: Page
    name: str = ''


def get_span_bbox(span: List) -> Bbox:
    """
    Calculate bounding box for a span.

    :param span:
    :return:
    """
    coords = [i.bbox for i in span]
    min_x0 = min((i.x0 for i in coords))
    min_y0 = min((i.y0 for i in coords))
    min_x1 = min((i.x1 for i in coords))
    min_y1 = min((i.y1 for i in coords))

    max_x0 = max((i.x0 for i in coords))
    max_y0 = max((i.y0 for i in coords))
    max_x1 = max((i.x1 for i in coords))
    max_y1 = max((i.y1 for i in coords))

    leftmost = min([min_x0, min_x1])
    rightmost = max([max_x0, max_x1])
    topmost = min([min_y0, min_y1])
    bottommost = max([max_y0, max_y1])
    bbox = Bbox(x0=leftmost, y0=topmost, x1=rightmost, y1=bottommost)
    return bbox


@dataclass
class Document:
    pages: List[Page]
    doc: Any
    @classmethod
    def from_mupdf(cls, path) -> Document:
        if isinstance(path, str):
            doc = fitz.open(path)
            return cls(pages=[Page.from_mupdf(page) for page in doc], doc=doc)

    @classmethod
    def from_pdfminer(cls, path) -> Document:
        if isinstance(path, str):
            pages = extract_pages(path)
            return cls([Page.from_pdfminer(page) for page in pages],doc=None)

    def create_sections(self):
        pass


@dataclass
class PyMuPDFAnnotation:
    border: Dict
    colors: Dict
    flags: int
    has_popup: bool
    info: Dict
    is_open: bool
    line_ends: tuple
    next_annotation: 'Annotation'
    opacity: float
    popup_rect: tuple
    popup_xref: int
    rect: tuple
    anno_type: tuple
    vertices: list
    xref: int

    @classmethod
    def from_annot(cls, annot: Dict):
        border = annot.border
        colors = annot.colors
        flags = annot.flags
        has_popup = annot.has_popup
        info = annot.info
        is_open = annot.is_open
        line_ends = annot.line_ends
        opacity = annot.opacity
        next_annotation = annot.next
        popup_rect = annot.popup_rect
        popup_xref = annot.popup_xref
        rect = annot.rect
        anno_type = annot.type
        vertices = annot.vertices
        xref = annot.xref

        return cls(border=border,
                   colors=colors,
                   flags=flags,
                   has_popup=has_popup,
                   info=info,
                   is_open=is_open,
                   line_ends=line_ends,
                   next_annotation=next_annotation,
                   opacity=opacity,
                   popup_rect=popup_rect,
                   popup_xref=popup_xref,
                   rect=rect,
                   anno_type=anno_type,
                   vertices=vertices,
                   xref=xref)


@dataclass
class PDFMinerAnnotation:
    subject: str
    flags: int
    color: List
    creation_date: str
    mod_date: str
    name: str
    author: str
    rect: List
    content: str

    @staticmethod
    def normalize_value(s):
        if s:
            return pdfminer.utils.decode_text(s)
        return s

    @classmethod
    def from_annot(cls, annot: Dict):
        subject = annot.get('Subj')
        flags = annot.get('F')
        color = annot.get('C')
        creation_date = annot.get('CreationDate')
        mod_date = annot.get('M') or annot.get('ModDate')
        rect = pdftypes.resolve1(annot.get('Rect'))
        author = annot.get('T')
        content = annot.get('Contents','')
        name = annot.get('NM')
        content, name, author, mod_date, creation_date, subject = [
            cls.normalize_value(i)
            for i in (content, name, author, mod_date, creation_date, subject)
        ]
        return cls(subject=subject,
                   flags=flags,
                   color=color,
                   creation_date=creation_date,
                   mod_date=mod_date,
                   rect=rect,
                   author=author,
                   content=content,
                   name=name)


@dataclass
class Annotation:
    content: str
    author: str
    mod_date: str
    creation_date: str
    rect: Bbox

    @classmethod
    def from_pymupdf_annot(cls, annot, orientation):
        content = annot.info.get('content')
        author = annot.info.get('title')
        name = annot.info.get('id')
        creation_date = annot.info.get('creationDate')
        mod_date = annot.info.get('modDate')
        subject = annot.info.get('subject')
        if orientation.bottom_is_zero:
            rect = Bbox.from_coords(*annot.rect, invert_y=True, page_height=orientation.page_height)
        else:
            rect = Bbox(*annot.rect)

        return cls(content=content,
                   author=author,
                   mod_date=mod_date,
                   creation_date=creation_date,
                   rect=rect)

    @classmethod
    def from_pdfminer_annot(cls, annot, orientation):
        if orientation.bottom_is_zero:
            rect = Bbox(*annot.rect)
        else:
            rect = Bbox.from_coords(
                coords=annot.rect, invert_y=True, page_height=orientation.page_height
            )
        return cls(content=annot.content,
                   author=annot.author,
                   mod_date=annot.mod_date,
                   creation_date=annot.creation_date,
                   rect=rect)

def line2str(line: List[Word]) -> str:
    return " ".join(map(str, line))

#Document.from_pdfminer(r'C:\projects\fohlio\hotels\holiday inn\new\20200218_HI_BALWM_Public_Space_FF&E_Specs_v2.2_CONFIDENT[1].pdf')
Document.from_mupdf(r'C:\projects\fohlio\hotels\holiday inn\new\20200218_HI_BALWM_Public_Space_FF&E_Specs_v2.2_CONFIDENT[1].pdf')