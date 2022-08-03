from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Tuple, List, Union

from pdfscraper.layout.utils import (
    Color,
    Bbox,
    PageOrientation,
    create_bbox_backend,
    Backend, Rectangular,
)


def get_pts(drawing: Dict) -> List:
    import fitz

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
class Drawing(Rectangular):
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


def cmyk_to_rgb(c, m, y, k, cmyk_scale=1, rgb_scale=1):
    r = rgb_scale * (1.0 - c / float(cmyk_scale)) * (1.0 - k / float(cmyk_scale))
    g = rgb_scale * (1.0 - m / float(cmyk_scale)) * (1.0 - k / float(cmyk_scale))
    b = rgb_scale * (1.0 - y / float(cmyk_scale)) * (1.0 - k / float(cmyk_scale))
    return r, g, b

def process_pdfminer_drawing(
    drawing: Union[
        "pdfminer.layout.LTRect", "pdfminer.layout.LTLine", "pdfminer.layout.LTCurve"
    ],
    page_orientation: PageOrientation,
) -> Shape:
    fill = drawing.fill
    fill_color = None
    stroke_color = None
    if fill:
        if hasattr(drawing.non_stroking_color, "__len__"):
            if len(drawing.non_stroking_color) == 1:
                drawing.non_stroking_color *= 3
            elif len(drawing.non_stroking_color) == 4:
                c,m,y,k = drawing.non_stroking_color
                drawing.non_stroking_color = cmyk_to_rgb(c,m,y,k)
            elif len(drawing.non_stroking_color) == 2:
                print(f'Unknown fill color detected {drawing.non_stroking_color}')
                drawing.non_stroking_color += [0]
            fill_color = Color(*drawing.non_stroking_color)
        else:
            if drawing.non_stroking_color:
                fill_color = Color(*[drawing.non_stroking_color] * 3)
            else:
                fill_color = Color(0, 0, 0)
    stroke = drawing.stroke
    if stroke:
        if hasattr(drawing.stroking_color, "__len__"):
            if len(drawing.stroking_color) == 1:
                drawing.stroking_color *= 3
            elif len(drawing.stroking_color) == 4:
                c,m,y,k=drawing.stroking_color
                drawing.stroking_color = cmyk_to_rgb(c,m,y,k)
            stroke_color = Color(*drawing.stroking_color)
        else:
            if drawing.stroking_color:
                stroke_color = Color(*[drawing.stroking_color] * 3)
            else:
                stroke_color = Color(0, 0, 0)
    # pdfminer has bottom as y-zero
    bbox = create_bbox_backend(
        backend=Backend.PDFMINER, coords=drawing.bbox, page_orientation=page_orientation
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
    import pdfminer

    if isinstance(drawing, pdfminer.layout.LTRect):
        return RectShape(**args)
    elif isinstance(drawing, pdfminer.layout.LTLine):
        return LineShape(**args)
    elif isinstance(drawing, pdfminer.layout.LTCurve):
        return CurveShape(**args)


def process_pymupdf_drawing(drawing: Dict, page_orientation: PageOrientation) -> Shape:
    items = drawing["items"]
    fill = "f" in drawing["type"]
    fill_color = Color(*drawing["fill"]) if fill else None
    stroke = "s" in drawing["type"]
    stroke_color = Color(*drawing["color"]) if stroke else None
    # mupdf has top as y-zero
    bbox = create_bbox_backend(
        backend=Backend.PYMUPDF, coords=drawing["rect"], page_orientation=page_orientation
    )

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
