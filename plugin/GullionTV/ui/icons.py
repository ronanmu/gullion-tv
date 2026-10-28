# -*- coding: utf-8 -*-
"""Material Symbols for the banner and INFO panel, at the size nearest the skin's.

Picture widgets can't scale a picture, so each icon is kept at a few sizes.
"""
import os

from . import scale

FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "images", "icons")
DESIGN_SIZE = 40
SIZES = (20, 27, 40, 80)
# Home's card icons and the colour-button circles are drawn at their own sizes.
CARD_SIZE, CARD_SIZES = 72, (36, 48, 72, 144)
KEY_SIZE, KEY_SIZES = 24, (12, 16, 24, 48)


def icon_path(name, design=DESIGN_SIZE, sizes=SIZES):
	size = min(sizes, key=lambda candidate: abs(candidate - scale.px(design)))
	return os.path.join(FOLDER, "%s_%d.png" % (name, size))


def card_icon(name):
	return icon_path(name, CARD_SIZE, CARD_SIZES)


def key_icon(colour):
	"""The filled circle for a colour button: "red", "green", "yellow" or "blue"."""
	return icon_path("key_" + colour, KEY_SIZE, KEY_SIZES)


# The red REC pill, drawn at these widths by tools/make_images.py (40 px high at 1920 wide).
PILL_W, PILL_H = 96, 40
PILL_SIZES = ((48, 20), (64, 27), (96, 40), (192, 80))


def rec_pill():
	width = scale.px(PILL_W)
	w, h = min(PILL_SIZES, key=lambda size: abs(size[0] - width))
	return os.path.join(FOLDER, "rec_pill_%dx%d.png" % (w, h))
