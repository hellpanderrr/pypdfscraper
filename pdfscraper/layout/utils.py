import itertools
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple, Iterable, NamedTuple, Dict

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal


@dataclass(frozen=True)
class VerticalOrientation:
    """
    Direction of a Y-axis. Bottom→Top or Top→Bottom.
    """

    bottom_is_zero: bool


@dataclass(frozen=True)
class HorizontalOrientation:
    """
    Direction of a X-axis. Left→Right or Right→Left.
    """

    left_is_zero: bool


@dataclass(frozen=True)
class Orientation:
    """
    Directions of X and Y axes.
    """

    vertical_orientation: VerticalOrientation
    horizontal_orientation: HorizontalOrientation

    @classmethod
    def create(cls, left_is_zero=True, bottom_is_zero=False):
        return cls(
            horizontal_orientation=HorizontalOrientation(left_is_zero=left_is_zero),
            vertical_orientation=VerticalOrientation(bottom_is_zero=bottom_is_zero),
        )


@dataclass(frozen=True)
class PageOrientation:
    """
    Directions of X/Y axes together with page dimensions.
    """

    orientation: Orientation
    page_height: float
    page_width: float

    @property
    def left_is_zero(self):
        return self.orientation.horizontal_orientation.left_is_zero

    @property
    def bottom_is_zero(self):
        return self.orientation.vertical_orientation.bottom_is_zero

    @classmethod
    def create(cls, left_is_zero=True, bottom_is_zero=False, page_width=None, page_height=None):
        orientation = Orientation(
            horizontal_orientation=HorizontalOrientation(left_is_zero=left_is_zero),
            vertical_orientation=VerticalOrientation(bottom_is_zero=bottom_is_zero),
        )
        return cls(orientation=orientation, page_height=page_height, page_width=page_width)


class Bbox(NamedTuple):
    """
    A rectangular bounding box.
    """

    x0: float
    y0: float
    x1: float
    y1: float

    def __str__(self) -> str:
        return f"Bbox(x0={self.x0:.2f},y0={self.y0:.2f},x1={self.x1:.2f},y1={self.y1:.2f})"

    def __eq__(self, other, decimals=1, n=4) -> bool:
        return [round(i, ndigits=decimals) for i in self[:n]] == [round(i, ndigits=decimals) for i in other[:n]]

    def move(self, delta=(0, 0, 0, 0)):
        return self + Bbox(*delta)

    def __add__(self, other: 'Bbox'):
        return Bbox(*[x + y for x, y in zip(self, other)])

    def isclose(self, other: 'Bbox', tolerance: float):
        """Check if two bboxes are close to each other."""
        return (
            abs(self.x0 - other.x0) < tolerance
            and abs(self.y0 - other.y0) < tolerance
            and abs(self.x1 - other.x1) < tolerance
            and abs(self.y1 - other.y1) < tolerance
        )

    def isinside(self, other: 'Bbox') -> bool:
        """Check if this bbox is inside another bbox."""
        return self.x0 >= other.x0 and self.y0 >= other.y0 and self.x1 <= other.x1 and self.y1 <= other.y1

    @property
    def height(self) -> float:
        return abs(self.y0 - self.y1)

    @property
    def width(self) -> float:
        return abs(self.x0 - self.x1)

    @classmethod
    def from_coords(cls, coords, invert_y=False, invert_x=False, page_height=None, page_width=None) -> "Bbox":
        x0, y0, x1, y1 = coords

        if invert_y:
            y0, y1 = page_height - y1, page_height - y0
        if invert_x:
            x0, x1 = page_width - x1, page_width - x0
        return cls(x0, y0, x1, y1)


class Rectangular:
    """
    An object with a rectangular bounding box.
    """

    bbox: Bbox

    def move(self, delta):
        attributes = {k: v for k, v in vars(self).items()}
        bbox = attributes.pop('bbox')
        attributes['bbox'] = bbox + Bbox(*delta)
        return type(self)(**attributes)

    @property
    def width(self):
        return self.bbox.width

    @property
    def height(self):
        return self.bbox.height

    @property
    def x0(self):
        return self.bbox.x0

    @property
    def x1(self):
        return self.bbox.x1

    @property
    def y0(self):
        return self.bbox.y0

    @property
    def y1(self):
        return self.bbox.y1


class Backend(Enum):
    PDFMINER = "pdfminer"
    PYMUPDF = "pymupdf"


DEFAULT_BACKEND_PAGE_ORIENTATIONS: Dict[Literal[Backend.PDFMINER, Backend.PYMUPDF], Orientation] = {
    Backend.PDFMINER: Orientation.create(bottom_is_zero=True, left_is_zero=True),
    Backend.PYMUPDF: Orientation.create(bottom_is_zero=False, left_is_zero=True),
}


def create_bbox_backend(backend: Backend, coords, page_orientation: PageOrientation) -> Bbox:
    """
    Creates a bbox taking into account axis direction from a given page.

    :param backend: backend type
    :param coords: 4-item sequence of x0,y0,x1,y1 coordinates
    :param page_orientation: page size together with X/Y axes directions.
    :return: a bounding box
    """
    bottom_is_zero = DEFAULT_BACKEND_PAGE_ORIENTATIONS[backend].vertical_orientation.bottom_is_zero
    left_is_zero = DEFAULT_BACKEND_PAGE_ORIENTATIONS[backend].horizontal_orientation.left_is_zero

    return Bbox.from_coords(
        coords=coords,
        invert_y=page_orientation.bottom_is_zero ^ bottom_is_zero,
        invert_x=page_orientation.left_is_zero ^ left_is_zero,
        page_height=page_orientation.page_height,
        page_width=page_orientation.page_width,
    )


@dataclass(frozen=True)
class Color:
    r: float
    g: float
    b: float

    def __eq__(self, other, decimals=1):
        if (
            round(self.r, decimals) == round(other.r, decimals)
            and round(self.b, decimals) == round(other.b, decimals)
            and round(self.g, decimals) == round(other.g, decimals)
        ):
            return True
        else:
            return False


def get_bbox(block) -> Tuple[float, float, float, float]:
    if hasattr(block, "bbox"):
        block = block.bbox
    if type(block) == dict and "rect" in block:
        block = block["rect"]
    x0, y0, x1, y1, *_ = block
    return x0, y0, x1, y1


def get_rightmost(block) -> float:
    x0, _, x1, _, *_ = get_bbox(block)
    return max(x0, x1)


def get_leftmost(block) -> float:
    x0, _, x1, _, *_ = get_bbox(block)
    return min(x0, x1)


def get_topmost(block) -> float:
    # top is zero
    _, y0, _, y1, *_ = get_bbox(block)
    return min(y0, y1)


def get_bottommost(block) -> float:
    # bottom is infinity
    _, y0, _, y1, *_ = get_bbox(block)
    return max(y0, y1)


def group_objs(words: List, gap: float = 5, decimals: int = 1, axis: str = 'y') -> List[List]:
    """
    Group words into vertically adjacent lines.

    First, create a dictionary with rounded y-coordinates as keys, and lists of words as values.
    Then merge together lists whose coordinate delta is <= gap.

    :param words: list of Words
    :param gap: vertical delta between lines to be merged.
    :param decimals: rounding precision.
    :param axis: horizontal (x) or vertical (y) grouping

    :return: vertically grouped lines, each line is sorted horizontally inside.

    """

    d = defaultdict(list)
    if axis == 'y':
        func = get_topmost
    else:
        func = get_leftmost

    for i in sorted(words, key=lambda x: round(func(x), decimals)):
        d[round(func(i), decimals)].append(i)
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
    total = [sorted(i, key=lambda x: get_leftmost(x) if axis == 'y' else get_topmost(x)) for i in total]
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
    string_groups = sum([["%s_%s" % (i, n) for i in g] for n, (k, g) in enumerate(itertools.groupby(df[col]))], [],)
    return df.groupby(string_groups, sort=False)
