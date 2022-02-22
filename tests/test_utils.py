import pytest

from pdfscraper.utils import group_objs_y
from pdfscraper.layout import  Word, Bbox, get_span_bbox

@pytest.fixture
def words():
    """
    Generate a list of vertically separated words.
    """
    objs = [Word(bbox=[0, 0, 0, 0]),
            Word(bbox=[0, 13, 0, 13]),
            Word(bbox=[0, 27, 0, 27]),
            Word(bbox=[0, 30, 0, 30]),
            Word(bbox=[0, 38, 0, 38]),
            Word(bbox=[0, 52, 0, 52]),
            Word(bbox=[0, 63, 0, 63]),
            Word(bbox=[0, 77, 0, 77]),
            Word(bbox=[0, 82, 0, 82]),
            Word(bbox=[0, 91, 0, 95])]
    return objs

def test_group_objs_y_1(words):
    expected_result = [[Word(bbox=[0, 0, 0, 0])],
                       [Word(bbox=[0, 13, 0, 13])],
                       [Word(bbox=[0, 27, 0, 27])],
                       [Word(bbox=[0, 30, 0, 30])],
                       [Word(bbox=[0, 38, 0, 38])],
                       [Word(bbox=[0, 52, 0, 52])],
                       [Word(bbox=[0, 63, 0, 63])],
                       [Word(bbox=[0, 77, 0, 77])],
                       [Word(bbox=[0, 82, 0, 82])],
                       [Word(bbox=[0, 91, 0, 95])]]
    assert group_objs_y(words, gap=1) == expected_result


def test_group_objs_y_5(words):
    expected_result = [[Word(bbox=[0, 0, 0, 0])],
                       [Word(bbox=[0, 13, 0, 13])],
                       [Word(bbox=[0, 27, 0, 27]), Word(bbox=[0, 30, 0, 30])],
                       [Word(bbox=[0, 38, 0, 38])],
                       [Word(bbox=[0, 52, 0, 52])],
                       [Word(bbox=[0, 63, 0, 63])],
                       [Word(bbox=[0, 77, 0, 77]), Word(bbox=[0, 82, 0, 82])],
                       [Word(bbox=[0, 91, 0, 95])]]
    assert group_objs_y(words, gap=5) == expected_result


def test_group_objs_y_15(words):
    expected_result = [[Word(bbox=[0, 0, 0, 0]),
                        Word(bbox=[0, 13, 0, 13]),
                        Word(bbox=[0, 27, 0, 27]),
                        Word(bbox=[0, 30, 0, 30]),
                        Word(bbox=[0, 38, 0, 38]),
                        Word(bbox=[0, 52, 0, 52]),
                        Word(bbox=[0, 63, 0, 63]),
                        Word(bbox=[0, 77, 0, 77]),
                        Word(bbox=[0, 82, 0, 82]),
                        Word(bbox=[0, 91, 0, 95])]]
    assert group_objs_y(words, gap=15) == expected_result


def test_get_span_bbox():
    objs = [Word(bbox=Bbox(x0=312.00, y0=531.95, x1=326.16, y1=544.07), text="real"),
            Word(bbox=Bbox(x0=326.16, y0=531.95, x1=329.70, y1=544.07), text=" "),
            Word(bbox=Bbox(x0=325.68, y0=531.95, x1=328.08, y1=544.07), text="-"),
            Word(bbox=Bbox(x0=328.08, y0=531.95, x1=330.48, y1=544.07), text=" "),
            Word(bbox=Bbox(x0=328.08, y0=531.95, x1=344.88, y1=544.07), text="time"),
            Word(bbox=Bbox(x0=344.88, y0=531.95, x1=349.08, y1=544.07), text=" "),
            Word(bbox=Bbox(x0=347.04, y0=531.95, x1=379.92, y1=544.07), text="operation"),
            Word(bbox=Bbox(x0=379.92, y0=531.95, x1=383.57, y1=544.07), text=" "),
            Word(bbox=Bbox(x0=384.48, y0=531.95, x1=389.28, y1=544.07), text="is"),
            Word(bbox=Bbox(x0=389.28, y0=531.95, x1=391.68, y1=544.07), text=" "),
            Word(bbox=Bbox(x0=393.12, y0=531.95, x1=405.12, y1=544.07), text="not"),
            Word(bbox=Bbox(x0=405.12, y0=531.95, x1=409.12, y1=544.07), text=" "),
            Word(bbox=Bbox(x0=407.52, y0=531.95, x1=438.72, y1=544.07), text="achieved"),
            Word(bbox=Bbox(x0=438.72, y0=531.95, x1=442.62, y1=544.07), text=" "),
            Word(bbox=Bbox(x0=439.92, y0=531.95, x1=442.32, y1=544.07), text="."),
            Word(bbox=Bbox(x0=442.32, y0=531.95, x1=444.72, y1=544.07), text=" ")]
    result = get_span_bbox(objs)
    assert result == Bbox(x0=312.0, y0=531.95, x1=444.72, y1=544.07)