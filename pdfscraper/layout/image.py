from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional, Any, Tuple, Iterable, Iterator

try:
    from typing import Literal, TypedDict
except ImportError:
    from typing_extensions import Literal, TypedDict  # type: ignore



from pdfscraper.layout.utils import Bbox, PageOrientation, create_bbox_backend, Backend

ImageSource = Literal["pdfminer", "mupdf"]


def get_image(layout_object) -> Optional['pdfminer.layout.LTImage']:
    import pdfminer
    if isinstance(layout_object, pdfminer.layout.LTImage):
        return layout_object
    elif isinstance(layout_object, pdfminer.layout.LTContainer):
        for child in layout_object:
            return get_image(child)
        return None
    else:
        return None


@contextmanager
def attr_as(obj, field: str, value) -> Iterator[None]:
    old_value = getattr(obj, field)
    setattr(obj, field, value)
    yield
    setattr(obj, field, old_value)


@dataclass(frozen=True)
class Image:
    """
    An image created from pdfminer or pymupdf object.

    """
    bbox: Bbox
    width: float
    height: float
    source_width: Optional[int]
    source_height: Optional[int]
    colorspace_name: Optional[str]
    bpc: Optional[int]
    xref: Optional[int]
    name: Optional[str]
    source: ImageSource
    raw_object: Any = None
    parent_object: Any = None
    colorspace_n: Optional[int] = None

    class Config:
        arbitrary_types_allowed = True

    def _save_pdfminer(self, path: str):
        from pdfminer.image import ImageWriter
        path, ext = os.path.splitext(path)
        path = os.path.abspath(path)
        folder, name = os.path.split(path)
        im = self.raw_object
        with attr_as(im, "name", name):
            return ImageWriter(folder).export_image(im)

    def _save_pymupdf(self, path: str):
        with open(path, "wb") as f:
            f.write(self.parent_object.extract_image(self.xref)["image"])

    def save(self, path: str):
        if self.source == "pdfminer":
            self._save_pdfminer(path)
        elif self.source == "mupdf":
            self._save_pymupdf(path)

    @classmethod
    def from_pdfminer(
            cls, image: 'pdfminer.layout.LTImage', orientation: PageOrientation
    ) -> 'Image':
        """
        Create an image out of pdfminer object.

        :param image: pdfminer LTImage object.
        :param orientation: page orientation data.
        :return:
        """
        from pdfminer.psparser import PSLiteral

        bbox = create_bbox_backend(backend=Backend.PDFMINER, coords=image.bbox, orientation=orientation)

        bpc = image.bits
        if hasattr(image.colorspace[0], "name"):
            colorspace_name = image.colorspace[0].name
        else:
            objs = image.colorspace[0].resolve()
            if type(objs) == PSLiteral:
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
    def from_pymupdf(
            cls, image: MuPDFImage, doc: 'fitz.fitz.Document', orientation: PageOrientation
    ) -> 'Image':
        raw_bbox = image.get("bbox")

        bbox = create_bbox_backend(backend=Backend.PYMUPDF, coords=raw_bbox, orientation=orientation)

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


def get_images_from_pymupdf_page(page) -> Iterable[MuPDFImage]:
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
