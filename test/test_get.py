import unittest
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import imagesize

image_dir = os.path.join(os.path.dirname(__file__), "images")


class GetTest(unittest.TestCase):
    def _test_from_file(self, filename: str, width: int, height: int):
        w, h = imagesize.get(os.path.join(image_dir, filename))
        self.assertEqual(w, width)
        self.assertEqual(h, height)

    def test_load_png(self):
        self._test_from_file("test.png", 802, 670)

    def test_load_jpeg(self):
        self._test_from_file("test.jpg", 802, 670)

    def test_load_jpeg2000(self):
        self._test_from_file("test.jp2", 802, 670)

    def test_load_gif(self):
        self._test_from_file("test.gif", 802, 670)

    def test_big_endian_tiff(self):
        self._test_from_file("test.tiff", 802, 670)

    def test_little_endian_tiff(self):
        self._test_from_file("multipage_tiff_example.tif", 800, 600)

    def test_load_bytes(self):
        with open(os.path.join(image_dir, "test.jpg"), "rb") as f:
            file_content = f.read()
        width, height = imagesize.get_from_bytes(file_content)
        self.assertEqual(width, 802)
        self.assertEqual(height, 670)

    def test_load_stream(self):
        with open(os.path.join(image_dir, "test.jpg"), "rb") as f:
            width, height = imagesize.get_from_file_stream(f)
        self.assertEqual(width, 802)
        self.assertEqual(height, 670)
