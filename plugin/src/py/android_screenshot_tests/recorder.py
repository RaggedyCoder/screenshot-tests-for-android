#!/usr/bin/env python
# Copyright 2014-present Facebook, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import xml.etree.ElementTree as ET
import os
import sys

from os.path import join
from PIL import Image, ImageChops

import common
import shutil
import tempfile


class VerifyError(Exception):
    pass


class Recorder:
    def __init__(self, input, output):
        self._input = input
        self._output = output
        self._realoutput = output
        self.diff_dir = os.path.dirname(output)

    def _get_image_size(self, file_name):
        with Image.open(file_name) as im:
            return im.size

    def _copy(self, name, w, h):
        tilewidth, tileheight = self._get_image_size(
            join(self._input,
                 common.get_image_file_name(name, 0, 0)))

        canvaswidth = 0

        for i in range(w):
            input_file = common.get_image_file_name(name, i, 0)
            canvaswidth += self._get_image_size(join(self._input, input_file))[0]

        canvasheight = 0

        for j in range(h):
            input_file = common.get_image_file_name(name, 0, j)
            canvasheight += self._get_image_size(join(self._input, input_file))[1]

        im = Image.new("RGBA", (canvaswidth, canvasheight))

        for i in range(w):
            for j in range(h):
                input_file = common.get_image_file_name(name, i, j)
                with Image.open(join(self._input, input_file)) as input_image:
                    im.paste(input_image, (i * tilewidth, j * tileheight))
                    input_image.close()

        im.save(join(self._output, name + ".png"))
        im.close()

    def _get_metadata_root(self):
        return ET.parse(join(self._input, "metadata.xml"))

    def _record(self):
        root = self._get_metadata_root()
        for screenshot in root.iter("screenshot"):
            self._copy(screenshot.find('name').text,
                       int(screenshot.find('tile_width').text),
                       int(screenshot.find('tile_height').text))

    def _clean(self):
        if os.path.exists(self._output):
            shutil.rmtree(self._output)
        os.makedirs(self._output)

    def _is_image_same(self,name, file1, file2):
        with Image.open(file1) as im1, Image.open(file2) as im2:
            assert im1.mode == im2.mode, "Different kinds of images."
            assert im1.size == im2.size, "Different sizes."

            pairs = zip(im1.getdata(), im2.getdata())
            if len(im1.getbands()) == 1:
                dif = sum(abs(p1 - p2) for p1, p2 in pairs)
            else:
                dif = sum(abs(c1 - c2) for p1, p2 in pairs for c1, c2 in zip(p1, p2))

            ncomponents = im1.size[0] * im1.size[1] * 3
            difference_percent = (dif / 255.0 * 100) / ncomponents
            is_passed = not (difference_percent > 0.05)
            if not is_passed:
                diff_image = self.get_difference(im1, im2)
                diff_image.save(join(self.diff_dir, name + ".png"))
            return is_passed

    def record(self):
        self._clean()
        self._record()

    def verify(self):
        self._output = tempfile.mkdtemp()
        self.diff_dir = join(os.path.dirname(self._output), "diff_image")
        if not os.path.exists(self.diff_dir):
            os.makedirs(self.diff_dir)
        self._record()
        test_result = []

        root = self._get_metadata_root()
        for screenshot in root.iter("screenshot"):
            name = screenshot.find('name').text + ".png"
            actual = join(self._output, name)
            expected = join(self._realoutput, name)
            test_class = screenshot.find('test_class').text
            test_method = screenshot.find('test_name').text
            is_passed = self._is_image_same(name, expected, actual)
            test_status = ET.SubElement(screenshot, 'test_status')
            test_status.text = str(is_passed)
        root.write("test_result.xml")
        shutil.rmtree(self._output)

    def get_difference(self, img1, img2):
        diff = ImageChops.difference(img1, img2)
        diff = diff.convert('L')
        return diff
