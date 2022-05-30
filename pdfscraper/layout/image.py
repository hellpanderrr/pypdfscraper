import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional, Literal, Any, Dict, Tuple, TypedDict, Iterable

import fitz
import pdfminer

from pdfscraper.layout.utils import Bbox, PageVerticalOrientation

ImageSource = Literal["pdfminer", "mupdf"]


def get_image(layout_object) -> Optional[pdfminer.layout.LTImage]:
    if isinstance(layout_object, pdfminer.layout.LTImage):
        return layout_object
    elif isinstance(layout_object, pdfminer.layout.LTContainer):
        for child in layout_object:
            return get_image(child)
    else:
        return None


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
    ) -> 'Image':
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
    ) -> 'Image':
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


def get_images_from_mupdf_page(page) -> Iterable[MuPDFImage]:
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
