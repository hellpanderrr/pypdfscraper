# from __future__ import annotations

import itertools
from typing import Union, List, Tuple

import unicodedata

from pdfscraper.layout.utils import Bbox, create_bbox_backend, Backend
from pdfscraper.layout.utils import (
    get_leftmost,
    get_rightmost,
    get_topmost,
    get_bottommost,
)


class Word:
    """
    A text string representing one word. It's generated from a line of text by splitting on a space.
    """

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

    @classmethod
    def from_pymupdf(cls, span: dict, orientation) -> "Span":
        words = [
            list(g)
            for k, g in (
                itertools.groupby(
                    span["chars"], key=lambda x: x["c"] not in (" ", "\xa0")
                )
            )
        ]
        new_words = []
        coords = []

        for word in words:
            x0, y0 = get_leftmost(word[0]["bbox"]), get_topmost(word[0]["bbox"])
            x1, y1 = get_rightmost(word[-1]["bbox"]), get_bottommost(word[-1]["bbox"])

            coords.append([x0, y0, x1, y1])
            text = "".join([c["c"] for c in word])

            # mupdf has top as zero and left as zero by default
            bbox = create_bbox_backend(
                backend=Backend.PYMUPDF,
                coords=(x0, y0, x1, y1),
                orientation=orientation,
            )

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
        return cls(words=new_words, bbox=bbox)

    @classmethod
    def from_pdfminer(cls, span: List["pdfminer.layout.LTChar"], orientation) -> "Span":
        """
        Convert a list of pdfminer characters into a Span.

        Split a list by space into Words.

        @param span: list of characters

        """
        import pdfminer

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

            bbox = create_bbox_backend(
                backend=Backend.PDFMINER,
                coords=(x0, y0, x1, y1),
                orientation=orientation,
            )

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
        return cls(words=new_words, bbox=bbox)


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
