import itertools
from collections import defaultdict
from typing import List, Tuple, Iterable

import fitz


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


def move_bbox(obj: tuple, delta: float = 1000):
    if not delta:
        return obj
    obj = list(obj)
    obj[1] += delta
    obj[3] += delta
    return obj


def move_rect(rect: fitz.fitz.Rect, delta: float):
    rect.y0 += delta
    rect.y1 += delta
    return rect


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
