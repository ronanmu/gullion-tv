# -*- coding: utf-8 -*-
"""Material Symbols for the banner and INFO panel, at the size nearest the skin's.

Picture widgets can't scale a picture, so each icon is kept at a few sizes.
"""
import os

from . import scale

FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "images", "icons")
DESIGN_SIZE = 40
SIZES = (20, 27, 40, 80)


def icon_path(name):
	size = min(SIZES, key=lambda candidate: abs(candidate - scale.px(DESIGN_SIZE)))
	return os.path.join(FOLDER, "%s_%d.png" % (name, size))
