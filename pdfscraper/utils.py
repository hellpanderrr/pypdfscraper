import io
import itertools
import os
from collections import defaultdict
from typing import NamedTuple, Union, List, Callable, Tuple, Iterable

import fitz
import pdfminer
import unicodedata
from pdfminer.layout import LTChar


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


class Bbox(NamedTuple):
    x0: float
    y0: float
    x1: float
    y1: float

    def __str__(self):
        return f'Bbox(x0={self.x0:.2f},y0={self.y0:.2f},x1={self.x1:.2f},y1={self.y1:.2f})'


class Word:
    __slots__ = ('text', 'bbox', 'font', 'size', 'color')

    def __init__(self,
                 text: str = '',
                 bbox: Union[Bbox, List[int], Tuple[int]] = None,
                 font: str = '',
                 size: str = '',
                 color=None,
                 normalize_text=False):
        self.text = text
        if normalize_text:
            self.text = self.text.replace('\xad', '-')
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
    __slots__ = ('words', 'bbox')

    def __init__(self, words: List[Word] = None, bbox: Bbox = None):
        """
        A collection of words.
        """
        self.words = words
        self.bbox = bbox

    @property
    def text(self):
        return ''.join([i.text for i in self.words])

    def __repr__(self):
        return 'Span <%s> %s' % ([round(i) for i in self.bbox], self.words)


class Line:
    __slots__ = ('bbox', 'spans')

    def __init__(self, bbox: List[float], spans):
        self.bbox = bbox
        self.spans = spans

    def __repr__(self):
        # '\n'.join([i.text for i in self.spans])
        return 'Line: %s' % self.spans

    @property
    def text(self):
        return ' '.join([i.text for i in self.spans])


class Block:
    __slots__ = ('bbox', 'lines')

    def __init__(self, bbox: Bbox, lines):
        """
        A collection spans.
        """
        self.bbox = bbox
        self.lines = lines

    def __repr__(self):
        return 'Block: %s' % self.lines


class Area:
    def __init__(self, words, drawings=None, line_gap=1):
        """
        A selection of words and drawings from a Page.
        """
        self.words = words
        self.drawings = drawings
        self.line_gap = line_gap

    def __repr__(self):
        return 'Area: %s' % ''.join([repr(i) + '\n' for i in self.words])

    def __iter__(self):
        return [i for i in self.words]

    def __add__(self, other) -> __qualname__:

        if isinstance(other, self.__class__):
            return self.__class__(self.words + other.words,
                                  self.drawings + other.drawings)
        else:
            raise TypeError()

    @property
    def sorted(self) -> List[List[Word]]:
        if self.words:
            return group_objs_y(self.words, gap=self.line_gap)
        return [[]]

    def select(self, condition: Callable) -> 'Area':
        """
        Find content matching condition.
        """
        ret = [i for i in self.words if condition(i)]
        drawings = [i for i in self.drawings if condition(i)]
        ret: self.__class__ = self.__class__(words=ret, drawings=drawings)
        return ret


class Page:
    def __init__(self,
                 blocks: List[Block],
                 parent_object: Union[pdfminer.layout.LTPage,
                                      fitz.fitz.Page] = None,
                 area_class=None,
                 delta: float = 0,
                 line_gap=1):
        """
        A page made out of pdfminer text boxes. It has boxes as blocks, and a
        a full list of words present on a page.

        @blocks: blocks of lines of chars
        @parent_object: pymupdf page
        @delta: how far this page's objects were moved vertically

        """
        self.blocks = blocks
        self.delta = delta
        self.line_gap = line_gap
        self.area_class = area_class
        if parent_object:
            if isinstance(parent_object, pdfminer.layout.LTPage):
                self.words = [word for block in self.blocks for line in block.lines
                              for word in line.words]
                self.drawings = [i for i in parent_object
                                 if issubclass(type(i), pdfminer.layout.LTCurve)]
                self.pdfminer_page = parent_object
            elif isinstance(parent_object, fitz.fitz.Page):
                self.words = [word for block in self.blocks for line in block.lines
                              for span in line.spans for word in span.words]
                self.fitz_page = parent_object
                self.drawings = parent_object.get_drawings()
                for i in self.drawings:
                    i['rect'] = move_rect(i['rect'], delta=delta)

    def __repr__(self):
        return 'Page: %s' % ''.join([repr(i) + '\n' for i in self.blocks])

    def select(self, condition: Callable) -> Area:
        """
        Find content matching condition.
        """
        words = [i for i in self.words if condition(i)]
        drawings = [i for i in self.drawings if condition(i)]
        ret = self.area_class(words=words, drawings=drawings, line_gap=self.line_gap)
        return ret

    @property
    def sorted(self) -> List[List[Word]]:
        return group_objs_y(self.words, gap=self.line_gap)


def group_objs_y(words: List[Word],
                 gap: float = 5,
                 decimals: int = 1) -> List[List[Word]]:
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


def get_center_group(group: List[Word]) -> float:
    """
    Get a middle point of a group of words.
    """

    left = get_leftmost(group[0])
    right = get_rightmost(group[-1])
    return (left + right) / 2


def get_center(obj: Word) -> float:
    """
    Get a middle point of a word.
    """
    return (obj.bbox.x0 + obj.bbox.x1) / 2


def get_span_bbox(span: List[Word]) -> Bbox:
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


def process_span_fitz(span: dict, move=None):
    words = [
        list(g) for k, g in (itertools.groupby(
            span['chars'], key=lambda x: x['c'] not in (' ', '\xa0')))
    ]
    new_words = []
    coords = []

    for word in words:
        x0, y0 = get_leftmost(word[0]['bbox']), get_topmost(word[0]['bbox'])
        x1, y1 = get_rightmost(word[-1]['bbox']), get_bottommost(
            word[-1]['bbox'])
        if move:
            y0 += move
            y1 += move
        coords.append([x0, y0, x1, y1])
        text = ''.join([c['c'] for c in word])

        new_words.append(
            Word(**{
                'text': text,
                'bbox': Bbox(x0=x0, y0=y0, x1=x1, y1=y1),
                'font': span['font'],
                'size': span['size'],
                'color': span['color']
            },
                 normalize_text=True))
    bbox = get_span_bbox(new_words)
    ret = Span(words=new_words, bbox=bbox)
    return ret


def process_span_pdfminer(span: List[LTChar],
                          move: float = None,
                          height: float = 0) -> Span:
    """
    Convert a list of pdfminer characters into a Span.

    Split a list by space into Words.

    @param span: list of characters
    @param move: add this value to y-coordinates
    @param height: page height
    """
    words = [
        list(g) for k, g in (itertools.groupby(
            span, key=lambda x: x.get_text() not in (' ', '\xa0')))
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
        text = ''.join([c.get_text() for c in word])
        font = word[0].fontname
        size = word[0].size

        new_words.append(
            Word(**{
                'text': text,
                'bbox': Bbox(x0=x0, y0=y0, x1=x1, y1=y1),
                'font': font,
                'size': size,
                'color': None
            },
                 normalize_text=True))
    bbox = get_span_bbox(new_words)
    ret = Span(words=new_words, bbox=bbox)
    return ret


def line2str(line: List[Word]) -> str:
    return ' '.join(map(str, line))


def flatten(items):
    """Yield items from any nested iterable."""
    for x in items:
        if isinstance(x, Iterable) and not isinstance(x, (str, bytes)):
            for sub_x in flatten(x):
                yield sub_x
        else:
            yield x


def convert_page_fitz(p: fitz.fitz.Page, move: float = 0, page_class=Page, area_class=Area) -> Page:
    blocks = p.get_text('rawdict', flags=3)['blocks']
    for block in blocks:
        for line in block['lines']:
            for j, span in enumerate(line['spans']):
                line['spans'][j] = process_span_fitz(span, move=move)
    for block in blocks:
        for k, line in enumerate(block['lines']):
            block['lines'][k] = Line(bbox=move_bbox(line['bbox'], move),
                                     spans=line['spans'])

    for n, block in enumerate(blocks):
        blocks[n] = Block(bbox=move_bbox(block['bbox'], move),
                          lines=block['lines'])

    page = page_class(blocks=blocks, parent_object=p, delta=move, area_class=area_class)
    return page


from PIL import Image


def convert_page_pdfminer(p: pdfminer.layout.LTPage) -> Page:
    """
    Convert pdfminer LTPage into a Page.

    @p: pdfminer page
    """

    blocks = []
    text_boxes = [i for i in p if hasattr(i, 'get_text')]
    for text_box in text_boxes:
        # get text lines
        lines = [
            text_line for text_line in text_box
            if hasattr(text_line, 'get_text')
        ]
        # convert lines into spans
        lines = [
            process_span_pdfminer(
                [i for i in line if type(i) != pdfminer.layout.LTAnno],
                height=p.height) for line in lines
        ]
        # make a block out of spans
        blocks.append(Block(bbox=Bbox(*text_box.bbox), lines=lines))
    page = Page(blocks=blocks, parent_object=p, delta=0)
    return page


def recoverpix(doc, item, ext='png'):
    xref = item[0]  # xref of PDF image
    smask = item[1]  # xref of its /SMask

    # special case: /SMask or /Mask exists
    # use Pillow to recover original image
    if smask > 0:
        fpx = io.BytesIO(  # BytesIO object from image binary
            doc.extract_image(xref)["image"],
        )
        fps = io.BytesIO(  # BytesIO object from smask binary
            doc.extract_image(smask)["image"],
        )
        img0 = Image.open(fpx)  # Pillow Image
        mask = Image.open(fps)  # Pillow Image
        # print(img0.size)
        if ext != 'png':
            img = Image.new("RGB", img0.size)
        else:
            img = Image.new("RGBA", img0.size)  # prepare result Image
        img.paste(img0, None, mask)  # fill in base image and mask
        bf = io.BytesIO()
        img.save(bf, ext, quality=0)  # save to BytesIO
        return {  # create dictionary expected by caller
            "ext": ext,
            "colorspace": 3,
            "image": bf.getvalue(),
        }

    # special case: /ColorSpace definition exists
    # to be sure, we convert these cases to RGB PNG images
    if "/ColorSpace" in doc.xref_object(xref, compressed=True):
        pix1 = fitz.Pixmap(doc, xref)
        pix2 = fitz.Pixmap(fitz.csRGB, pix1)
        return {  # create dictionary expected by caller
            "ext": ext,
            "colorspace": 3,
            "image": pix2.tobytes(ext),
        }
    return doc.extract_image(xref)


def groupby_consec(df, col):
    string_groups = sum([['%s_%s' % (i, n) for i in g]
                         for n, (k, g) in enumerate(itertools.groupby(df[col]))], [])
    return df.groupby(string_groups, sort=False)


def save_image(img, doc, path, name, page_number=0, spec='', ext='png', number=0, master_name=''):
    image = recoverpix(doc, img, ext=ext)
    n = image["colorspace"]
    imgdata = image["image"]
    if master_name:
        final_name = os.path.join(path, master_name + ext)
    else:
        print(os.path.join(path, "%s_page=%s_number=%s_spec=%s.%s" %
                           (name, page_number, number + 1, spec.strip(), ext)))
        final_name = os.path.join(path, "%s_page=%s_number=%s_spec=%s.%s" %
                                  (name, page_number, number + 1, spec.strip(), ext))

    imgfile = os.path.join(final_name)
    fout = open(imgfile, "wb")
    fout.write(imgdata)
    fout.close()
    return final_name
