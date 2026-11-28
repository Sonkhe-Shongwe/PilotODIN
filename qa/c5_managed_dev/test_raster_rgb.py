"""Standard-library tests; no PDFium/Pillow imports or native rendering."""
import ctypes
import unittest
from types import SimpleNamespace

from qa.c5_managed_dev.raster_rgb import packed_rgb


def bitmap(raw, *, width=2, height=2, stride=6, **changes):
    fields = dict(width=width, height=height, stride=stride, mode="RGB",
                  n_channels=3, rev_byteorder=True, buffer=bytearray(raw))
    fields.update(changes)
    return SimpleNamespace(**fields)


class PackedRGBTests(unittest.TestCase):
    def test_exact_rgb_channel_order_and_copy(self):
        pixels = bytes((255,0,0,0,255,0,0,0,255,12,34,56))
        data = bitmap(pixels)
        result = packed_rgb(data,(2,2))
        self.assertEqual(result,pixels)
        data.buffer[:] = b"\0"*12
        self.assertEqual(result,pixels)
        self.assertIs(type(result),bytes)

    def test_ctypes_pdfium_buffer_shape(self):
        pixels = bytes(range(12))
        data = bitmap(pixels,buffer=(ctypes.c_ubyte*12).from_buffer_copy(pixels))
        self.assertEqual(packed_rgb(data,(2,2)),pixels)

    def test_stride_padding_is_not_pixel_data(self):
        pixels = bytes(range(12))
        data = bitmap(pixels[:6]+b"\xaa\xbb"+pixels[6:]+b"\xcc\xdd",stride=8)
        self.assertEqual(packed_rgb(data,(2,2)),pixels)
        with self.assertRaisesRegex(ValueError,"Blank"):
            packed_rgb(bitmap(b"\xff"*6+b"\0\0"+b"\xff"*6+b"\0\0",stride=8),(2,2))

    def test_reject_blank(self):
        with self.assertRaisesRegex(ValueError,"Blank"):
            packed_rgb(bitmap(b"\xff"*12),(2,2))

    def test_reject_wrong_format_and_geometry(self):
        for data in (bitmap(b"\0"*12,mode="BGR"),bitmap(b"\0"*12,n_channels=4),
                     bitmap(b"\0"*12,rev_byteorder=False),bitmap(b"\0"*12,width=3)):
            with self.subTest(data=data), self.assertRaises(ValueError):
                packed_rgb(data,(2,2))

    def test_reject_bad_stride_or_buffer(self):
        for data in (bitmap(b"\0"*10,stride=5),bitmap(b"\0"*11),
                     bitmap(b"\0"*13),bitmap(b"",buffer=memoryview(bytearray(24))[::2])):
            with self.subTest(data=data), self.assertRaises(ValueError):
                packed_rgb(data,(2,2))
