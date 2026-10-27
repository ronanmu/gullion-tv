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


# Material Symbols (Apache 2.0) for the banner and INFO panel. The font isn't kept in
# the repository; fetch it once and pass its folder:
#   https://github.com/google/material-design-icons/tree/master/variablefont
#   MATERIAL=/path/to/folder python3 tools/make_images.py
ICONS = {
	"hd": "hd", "uhd": "4k", "subtitles": "subtitles", "audio_description": "audio_description",
	"sign_language": "sign_language", "repeat": "replay",
	"satellite": "satellite_alt", "terrestrial": "cell_tower", "cable": "cable", "internet": "language",
	"sound": "volume_up", "subtitles_off": "subtitles_off", "check": "check",
}
# Drawn dark too, for use on a highlighted (light) row.
ON_LIGHT = ("check", "audio_description", "subtitles", "subtitles_off")
ICON_SIZES = (20, 27, 40, 80)  # 40 px at 1920 wide


def material_icons(folder, out):
	from PIL import ImageFont
	font_path = os.path.join(folder, "MaterialSymbolsOutlined[FILL,GRAD,opsz,wght].ttf")
	if not os.path.isfile(font_path):
		font_path = os.path.join(folder, "MaterialSymbolsOutlined.ttf")
	codepoints = {}
	for name in ("MaterialSymbolsOutlined[FILL,GRAD,opsz,wght].codepoints", "codepoints"):
		if os.path.isfile(os.path.join(folder, name)):
			codepoints = dict(line.split() for line in open(os.path.join(folder, name)) if line.strip())
			break
	if not os.path.isdir(out):
		os.makedirs(out)
	for size in ICON_SIZES:
		big = size * SUPERSAMPLE
		font = ImageFont.truetype(font_path, big)
		font.set_variation_by_axes([0, 0, 48, 400])  # outlined, regular weight
		drawn = [(name, symbol, theme.TEXT) for name, symbol in sorted(ICONS.items())]
		drawn += [(name + "_on_light", ICONS[name], theme.TEXT_ON_SELECTED) for name in ON_LIGHT]
		for name, symbol, colour in drawn:
			image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
			glyph = chr(int(codepoints[symbol], 16))
			ImageDraw.Draw(image).text((big / 2.0, big / 2.0), glyph, font=font, fill=_rgba(colour), anchor="mm")
			path = os.path.join(out, "%s_%d.png" % (name, size))
			image.resize((size, size), Image.LANCZOS).save(path)
			print(path)


if __name__ == "__main__":
	if not os.path.isdir(OUT):
		os.makedirs(OUT)
	# One size per common skin: 26 px at 1920 wide, 17 at 1280, 13 and 10 for smaller skins, 52 for 4K.
	for size in (10, 13, 17, 26, 52):
		clock(os.path.join(OUT, "rec_clock_%d.png" % size), size, theme.KEY_RED, theme.TEXT)
	if os.environ.get("MATERIAL"):
		material_icons(os.environ["MATERIAL"], os.path.join(OUT, "icons"))
