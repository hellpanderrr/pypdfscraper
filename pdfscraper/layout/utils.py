import itertools
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Tuple, Iterable, NamedTuple

import fitz
from pydantic import confloat


@dataclass(frozen=True)
class PageVerticalOrientation:
    bottom_is_zero: bool
    page_height: float


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


class Bbox(NamedTuple):
    """
    A rectangular bounding box.
    """

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


def get_bbox(block) -> Tuple[float, float, float, float]:
    if hasattr(block, 'bbox'):
        block = block.bbox
    if type(block) == dict and 'rect' in block:
        block = block['rect']
    x0, y0, x1, y1, *_ = block
    return x0, y0, x1, y1


def get_rightmost(block) -> float:
    x0, y0, x1, y1, *_ = get_bbox(block)
    return max(x0, x1)


def get_leftmost(block) -> float:
    x0, y0, x1, y1, *_ = get_bbox(block)
    return min(x0, x1)


def get_topmost(block) -> float:
    # top is zero
    x0, y0, x1, y1, *_ = get_bbox(block)
    return min(y0, y1)


def get_bottommost(block) -> float:
    # bottom is infinity
    x0, y0, x1, y1, *_ = get_bbox(block)
    return max(y0, y1)


def group_objs_y(words: List,
                 gap: float = 5,
                 decimals: int = 1) -> List[List]:
    """
    Group words into vertically adjacent lines.

    First, create a dictionary with rounded y-coordinates as keys, and lists of words as values.
    Then merge together lists whose coordinate delta is <= gap.

    @param words: list of Words
    @param gap: vertical delta between lines to be merged.
    @param decimals: rounding precision.

    @returns: vertically grouped lines, each line is sorted horizontally inside.

    """

    d = defaultdict(list)

    for i in sorted(words, key=lambda x: round(get_topmost(x), decimals)):
        d[round(get_topmost(i), decimals)].append(i)
    lines = list(d.items())
    total = []
    curr_group = [lines[0][1]]
    for n, (y, i) in enumerate(lines):
        if n == 0:
            continue
        left = lines[n - 1][0]
        right = y
        dist = abs(left - right)
        if dist <= gap:
            curr_group.append(i)
        else:
            total.append(sum(curr_group, []))
            curr_group = [i]
    total.append(sum(curr_group, []))

    # sort every line horizontally
    total = [sorted(i, key=lambda x: get_leftmost(x)) for i in total]
    return total





def get_center_group(group: List) -> float:
    """
    Get a middle point of a group of words.
    """

    left = get_leftmost(group[0])
    right = get_rightmost(group[-1])
    return (left + right) / 2


def get_center(obj) -> float:
    """
    Get a middle point of a word.
    """
    return (obj.bbox.x0 + obj.bbox.x1) / 2


def flatten(items):
    """Yield items from any nested iterable."""
    for x in items:
        if isinstance(x, Iterable) and not isinstance(x, (str, bytes)):
            for sub_x in flatten(x):
                yield sub_x
        else:
            yield x


def groupby_consec(df, col):
    string_groups = sum([['%s_%s' % (i, n) for i in g]
                         for n, (k, g) in enumerate(itertools.groupby(df[col]))], [])
    return df.groupby(string_groups, sort=False)
