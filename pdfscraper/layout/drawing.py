from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Tuple, List, Union

import fitz
import pdfminer
import pdfminer.layout

from pdfscraper.layout.utils import Color, Bbox, PageOrientation, create_bbox_backend, Backend


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


@dataclass(frozen=True)
class Point:
    x: float
    y: float


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


Shape = Union[LineShape, RectShape, CurveShape]


def process_pdfminer_drawing(
        drawing: Union['pdfminer.layout.LTRect', 'pdfminer.layout.LTLine', 'pdfminer.layout.LTCurve'],
        orientation: PageOrientation) -> Shape:
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
                fill_color = Color(*[drawing.non_stroking_color] * 3)
            else:
                fill_color = Color(0, 0, 0)
    stroke = drawing.stroke
    if stroke:
        if len(drawing.stroking_color) == 1:
            drawing.stroking_color *= 3
        stroke_color = Color(*drawing.stroking_color)
    # pdfminer has bottom as y-zero
    bbox = create_bbox_backend(backend=Backend.PDFMINER, coords=drawing.bbox, orientation=orientation)

    pts = None  # drawing.pts
    args = {
        "fill": fill,
        "fill_color": fill_color,
        "stroke": stroke,
        "stroke_color": stroke_color,
        "bbox": bbox,
        "points": pts,
    }
    if isinstance(drawing, pdfminer.layout.LTRect):
        return RectShape(**args)
    elif isinstance(drawing, pdfminer.layout.LTLine):
        return LineShape(**args)
    elif isinstance(drawing, pdfminer.layout.LTCurve):
        return CurveShape(**args)


def process_pymupdf_drawing(drawing: Dict, orientation: PageOrientation) -> Shape:
    items = drawing["items"]
    fill = "f" in drawing["type"]
    fill_color = Color(*drawing["fill"]) if fill else None
    stroke = "s" in drawing["type"]
    stroke_color = Color(*drawing["color"]) if stroke else None
    # mupdf has top as y-zero
    bbox = create_bbox_backend(backend=Backend.PYMUPDF, coords=drawing["rect"], orientation=orientation)

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
