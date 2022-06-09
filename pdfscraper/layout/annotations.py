from dataclasses import dataclass
from typing import Dict, List

import fitz  # type: ignore
import pdfminer

from .utils import Bbox, create_bbox_backend, Backend


@dataclass
class PyMuPDFAnnotation:
    border: Dict
    colors: Dict
    flags: int
    has_popup: bool
    info: Dict
    is_open: bool
    line_ends: tuple
    next_annotation: 'Annotation'
    opacity: float
    popup_rect: tuple
    popup_xref: int
    rect: tuple
    anno_type: tuple
    vertices: list
    xref: int

    @classmethod
    def from_annot(cls, annot: fitz.fitz.Annot):
        border = annot.border
        colors = annot.colors
        flags = annot.flags
        has_popup = annot.has_popup
        info = annot.info
        is_open = annot.is_open
        line_ends = annot.line_ends
        opacity = annot.opacity
        next_annotation = annot.next
        popup_rect = annot.popup_rect
        popup_xref = annot.popup_xref
        rect = annot.rect
        anno_type = annot.type
        vertices = annot.vertices
        xref = annot.xref

        return cls(border=border,
                   colors=colors,
                   flags=flags,
                   has_popup=has_popup,
                   info=info,
                   is_open=is_open,
                   line_ends=line_ends,
                   next_annotation=next_annotation,
                   opacity=opacity,
                   popup_rect=popup_rect,
                   popup_xref=popup_xref,
                   rect=rect,
                   anno_type=anno_type,
                   vertices=vertices,
                   xref=xref)


@dataclass
class PDFMinerAnnotation:
    subject: str
    flags: int
    color: List
    creation_date: str
    mod_date: str
    name: str
    author: str
    rect: List
    content: str

    @staticmethod
    def normalize_value(s):
        if s:
            return pdfminer.utils.decode_text(s)
        return s

    @classmethod
    def from_annot(cls, annot: Dict):
        subject = annot.get('Subj')
        flags = int(annot.get('F'))

        # flags = int(flags) if flags else flags
        color = annot.get('C')
        creation_date = annot.get('CreationDate')
        mod_date = annot.get('M') or annot.get('ModDate')
        rect = pdfminer.pdftypes.resolve1(annot.get('Rect'))
        author = annot.get('T')
        content = annot.get('Contents', '')
        name = annot.get('NM')
        content, name, author, mod_date, creation_date, subject = [
            cls.normalize_value(i)
            for i in (content, name, author, mod_date, creation_date, subject)
        ]
        return cls(subject=subject,
                   flags=flags,
                   color=color,
                   creation_date=creation_date,
                   mod_date=mod_date,
                   rect=rect,
                   author=author,
                   content=content,
                   name=name)


@dataclass
class Annotation:
    content: str
    author: str
    mod_date: str
    creation_date: str
    rect: Bbox

    @classmethod
    def from_pymupdf_annot(cls, annot, orientation):
        content = annot.info.get('content')
        author = annot.info.get('title')
        name = annot.info.get('id')
        creation_date = annot.info.get('creationDate')
        mod_date = annot.info.get('modDate')
        subject = annot.info.get('subject')

        rect = create_bbox_backend(backend=Backend.PYMUPDF, coords=annot.rect, orientation=orientation)

        return cls(content=content,
                   author=author,
                   mod_date=mod_date,
                   creation_date=creation_date,
                   rect=rect)

    @classmethod
    def from_pdfminer_annot(cls, annot, orientation):
        rect = create_bbox_backend(backend=Backend.PDFMINER, coords=annot.rect, orientation=orientation)

        return cls(content=annot.content,
                   author=annot.author,
                   mod_date=annot.mod_date,
                   creation_date=annot.creation_date,
                   rect=rect)
