"""Generate the plugin's small images from the theme colours.

	pip install pillow
	python3 tools/make_images.py        # writes plugin/GullionTV/images/*.png
"""
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "plugin", "GullionTV"))
import theme  # noqa: E402  plain module, no enigma2 imports

OUT = os.path.join(ROOT, "plugin", "GullionTV", "images")
SUPERSAMPLE = 8


def _rgba(colour):
	return tuple((theme.rgb(colour) >> shift) & 0xff for shift in (16, 8, 0)) + (255,)


def clock(path, size, face, hands):
	"""A filled clock face with hands at three o'clock, on a transparent background."""
	big = size * SUPERSAMPLE
	image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
	draw = ImageDraw.Draw(image)
	draw.ellipse((0, 0, big - 1, big - 1), fill=_rgba(face))
	centre = big / 2.0
	width = int(big * 0.11)
	draw.line((centre, centre, centre, big * 0.2), fill=_rgba(hands), width=width)
	draw.line((centre, centre, big * 0.74, centre), fill=_rgba(hands), width=width)
	draw.ellipse((centre - width * 0.7, centre - width * 0.7, centre + width * 0.7, centre + width * 0.7), fill=_rgba(hands))
	image.resize((size, size), Image.LANCZOS).save(path)
	print(path)


if __name__ == "__main__":
	if not os.path.isdir(OUT):
		os.makedirs(OUT)
	clock(os.path.join(OUT, "rec_clock.png"), 26, theme.KEY_RED, theme.TEXT)
