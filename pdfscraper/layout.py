import itertools
import os
from contextlib import contextmanager
from typing import Literal
from typing import Optional
from typing import Union, List, Callable, Tuple, Dict, Any, NamedTuple

import fitz
import pdfminer
import unicodedata
from pdfminer.high_level import extract_pages
from pdfminer.image import ImageWriter
from pdfminer.layout import LTChar
from pydantic import confloat
from dataclasses import dataclass

from pdfscraper.utils import (
    group_objs_y,
    get_leftmost,
    get_rightmost,
    get_topmost,
    get_bottommost,
)

ImageSource = Literal["pdfminer", "mupdf"]


@dataclass
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


@dataclass
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


@dataclass
class Drawing:
    bbox: Bbox
    fill_color: Optional[Color]
    stroke_color: Optional[Color]
    fill: bool
    stroke: bool


#     height: PositiveFloat
#     width: PositiveFloat


@dataclass
class RectShape(Drawing):
    points: Optional[Tuple[Point, Point, Point, Point]]


@dataclass
class LineShape(Drawing):
    points: Optional[Tuple[Point, Point]]


@dataclass
class CurveShape(Drawing):
    points: Optional[Tuple[Point, Point, Point, Point]]


from pdfminer.layout import LTRect, LTLine, LTCurve


def get_pts(drawing: Dict):
    ret = []
    for i in drawing["items"]:
        for j in i[1:]:
            if isinstance(j, fitz.fitz.Rect):
                ret.append(j.bl)
                ret.append(j.br)
            else:
                ret.append(j)
    return ret


def process_pdfminer_drawing(drawing: Union[LTRect, LTLine, LTCurve], orientation):
    fill = drawing.fill
    fill_color = Color(*drawing.non_stroking_color) if fill else None
    stroke = drawing.stroke
    stroke_color = Color(*drawing.stroking_color) if stroke else None
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


def process_mupdf_drawing(drawing: Dict, orientation):
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



@dataclass
class PageVerticalOrientation:
    bottom_is_zero: bool
    page_height: float


@contextmanager
def attr_as(obj, field: str, value) -> None:
    old_value = getattr(obj, field)
    setattr(obj, field, value)
    yield
    setattr(obj, field, old_value)


@dataclass
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
        folder, name = os.path.split(path)
        im = self.raw_object
        with attr_as(im, "name", name):
            return ImageWriter(folder).export_image(im)

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
    ):
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
    ):
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


def get_images_from_mupdf_page(page):
    images = page.get_images()
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
    ) in images:
        bbox = page.get_image_bbox(name)
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


def process_span_fitz(span: dict, move=None):
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
        if move:
            y0 += move
            y1 += move
        coords.append([x0, y0, x1, y1])
        text = "".join([c["c"] for c in word])

        new_words.append(
            Word(
                **{
                    "text": text,
                    "bbox": Bbox(x0=x0, y0=y0, x1=x1, y1=y1),
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
    span: List[LTChar], move: float = None, height: float = 0
) -> Span:
    """
    Convert a list of pdfminer characters into a Span.

    Split a list by space into Words.

    @param span: list of characters
    @param move: add this value to y-coordinates
    @param height: page height
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
        x0, y0 = word[0].x0, word[0].y1
        x1, y1 = word[-1].x1, word[-1].y0
        if move:
            y0 += move
            y1 += move
        y0 = height - y0
        y1 = height - y1
        coords.append([x0, y0, x1, y1])
        text = "".join([c.get_text() for c in word])
        font = word[0].fontname
        size = word[0].size

        new_words.append(
            Word(
                **{
                    "text": text,
                    "bbox": Bbox(x0=x0, y0=y0, x1=x1, y1=y1),
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


def get_image(layout_object):
    if isinstance(layout_object, pdfminer.layout.LTImage):
        return layout_object
    if isinstance(layout_object, pdfminer.layout.LTContainer):
        for child in layout_object:
            return get_image(child)
    else:
        return None


class Page:
    def __init__(self, words, drawings, images, raw_object):

        self.words = words
        self.drawings = drawings
        self.images = images
        self.raw_object = raw_object

    def __repr__(self):
        return "Page: %s" % "".join([repr(i) + "\n" for i in self.words])

    def select(self, condition: Callable):
        """
        Find content matching condition.
        """
        words = [i for i in self.words if condition(i)]
        drawings = [i for i in self.drawings if condition(i)]
        ret = Page(words=words, drawings=drawings)
        return ret

    @property
    def sorted(self) -> List[List[Word]]:
        return group_objs_y(self.words)

    @classmethod
    def from_mupdf(cls, page: fitz.fitz.Page):
        blocks = page.get_text("rawdict", flags=3)["blocks"]
        for block in blocks:
            for line in block["lines"]:
                for j, span in enumerate(line["spans"]):
                    line["spans"][j] = process_span_fitz(span)
        for block in blocks:
            for k, line in enumerate(block["lines"]):
                block["lines"][k] = Line(bbox=(line["bbox"]), spans=line["spans"])

        for n, block in enumerate(blocks):
            blocks[n] = Block(bbox=(block["bbox"]), lines=block["lines"])

        drawings = sorted(page.get_drawings(), key=lambda x: x["rect"][1])
        orientation = PageVerticalOrientation(
            bottom_is_zero=False, page_height=Bbox(*page.rect).height
        )
        drawings = [process_mupdf_drawing(i, orientation) for i in drawings]
        words = [
            word
            for block in blocks
            for line in block.lines
            for span in line.spans
            for word in span.words
        ]
        drawings = sorted(drawings, key=get_topmost)
        images = get_images_from_mupdf_page(page)
        page = Page(words=words, drawings=drawings, images=images, raw_object=page)

        return page

    @classmethod
    def from_pdfminer(cls, page: pdfminer.layout.LTPage) -> "Page":
        blocks = []
        text_boxes = [i for i in page if hasattr(i, "get_text")]
        for text_box in text_boxes:
            # get text lines
            lines = [
                text_line for text_line in text_box if hasattr(text_line, "get_text")
            ]
            # convert lines into spans
            lines = [
                process_span_pdfminer(
                    [i for i in line if type(i) != pdfminer.layout.LTAnno],
                    height=page.height,
                )
                for line in lines
            ]
            # make a block out of spans
            blocks.append(Block(bbox=Bbox(*text_box.bbox), lines=lines))
        words = [
            word for block in blocks for line in block.lines for word in line.words
        ]
        drawings = [i for i in page if issubclass(type(i), pdfminer.layout.LTCurve)]
        orientation = PageVerticalOrientation(
            bottom_is_zero=False, page_height=page.height
        )
        drawings = [process_pdfminer_drawing(i, orientation) for i in drawings]
        drawings = sorted(drawings, key=get_topmost)
        images = filter(bool, map(get_image, page))
        for image in images:
            im = Image.from_pdfminer(image, orientation)

        page = Page(words=words, images=images, drawings=drawings, raw_object=page)
        return page


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


def line2str(line: List[Word]) -> str:
    return " ".join(map(str, line))


path = r"C:\projects\test2.pdf"
doc = fitz.open(path)
fitz_page = doc[0]

pdfminer_page = list(extract_pages(path))[0]
print(
    list(
        zip(
            Page.from_mupdf(fitz_page).drawings,
            Page.from_pdfminer(pdfminer_page).drawings,
        )
    )
)
