"""Generate the plugin's icons from Material Symbols, in the theme colours.

	pip install pillow
	MATERIAL=/path/to/symbols MDI=/path/to/mdi REC_FONT=/path/to/OpenSans.ttf python3 tools/make_images.py
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


# Home's cards (72 px at 1920 wide), drawn light, and dark for the highlighted card.
CARD_ICONS = {"recordings": "video_library", "webcams": "videocam"}
# Two cards use the community Material Design Icons set (Pictogrammers Free License; the
# icons are Apache 2.0) instead. Fetch @mdi/font once and pass its folder as MDI:
#   https://cdn.jsdelivr.net/npm/@mdi/font@7.4.47/  (fonts/*.ttf and css/*.css)
MDI_CARD_ICONS = {"live_tv": "television-classic", "tv_guide": "television-guide"}
CARD_SIZES = (36, 48, 72, 144)
# The colour-button hints: a filled circle in each key's colour, 24 px at 1920 wide.
KEY_COLOURS = {"red": theme.KEY_RED, "green": theme.KEY_GREEN, "yellow": theme.KEY_YELLOW, "blue": theme.KEY_BLUE}
KEY_SIZES = (12, 16, 24, 48)
# A recording in the guide: MDI's record-circle in red, 26 px at 1920 wide (list cells can't scale pictures).
REC_SIZES = (10, 13, 17, 26, 52)


# The REC pill: a red rounded bar with REC in bold white, 96x40 at 1920 wide. The text is part
# of the picture so it's bold on any skin. REC_FONT is Open Sans from Google Fonts (SIL Open
# Font License): https://github.com/google/fonts/tree/main/ofl/opensans, drawn at Bold.
PILL = (96, 40)
PILL_SCALES = (0.5, 2 / 3.0, 1, 2)


def pills(out, font_path):
	from PIL import ImageFont
	for factor in PILL_SCALES:
		w, h = int(round(PILL[0] * factor)), int(round(PILL[1] * factor))
		image = Image.new("RGBA", (w * SUPERSAMPLE, h * SUPERSAMPLE), (0, 0, 0, 0))
		draw = ImageDraw.Draw(image)
		draw.rounded_rectangle((0, 0, w * SUPERSAMPLE - 1, h * SUPERSAMPLE - 1), h * SUPERSAMPLE // 2, fill=_rgba(theme.KEY_RED))
		font = ImageFont.truetype(font_path, int(h * SUPERSAMPLE * 0.6))
		if b"Bold" in (font.get_variation_names() if hasattr(font, "get_variation_names") else []):
			font.set_variation_by_name("Bold")
		draw.text((w * SUPERSAMPLE / 2.0, h * SUPERSAMPLE / 2.0), "REC", font=font, fill=(255, 255, 255, 255), anchor="mm")
		path = os.path.join(out, "rec_pill_%dx%d.png" % (w, h))
		image.resize((w, h), Image.LANCZOS).save(path)
		print(path)


def mdi_codepoints(css):
	"""{"television-guide": 0xF0503} from the @mdi/font stylesheet."""
	import re
	return dict((name, int(code, 16)) for name, code in
		re.findall(r'\.mdi-([a-z0-9-]+)::before\s*\{\s*content:\s*"\\([0-9A-Fa-f]+)"', open(css).read()))


def mdi_icons(folder, out):
	from PIL import ImageFont
	font_path = os.path.join(folder, "materialdesignicons-webfont.ttf")
	codepoints = mdi_codepoints(os.path.join(folder, "materialdesignicons.css"))
	for size in CARD_SIZES:
		big = size * SUPERSAMPLE
		font = ImageFont.truetype(font_path, big)
		for name, symbol in sorted(MDI_CARD_ICONS.items()):
			for suffix, colour in (("", theme.TEXT), ("_on_light", theme.TEXT_ON_SELECTED)):
				image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
				ImageDraw.Draw(image).text((big / 2.0, big / 2.0), chr(codepoints[symbol]), font=font, fill=_rgba(colour), anchor="mm")
				path = os.path.join(out, "%s%s_%d.png" % (name, suffix, size))
				image.resize((size, size), Image.LANCZOS).save(path)
				print(path)
	for size in REC_SIZES:
		big = size * SUPERSAMPLE
		font = ImageFont.truetype(font_path, big)
		image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
		ImageDraw.Draw(image).text((big / 2.0, big / 2.0), chr(codepoints["record-circle"]), font=font, fill=_rgba(theme.KEY_RED), anchor="mm")
		path = os.path.join(out, "record_%d.png" % size)
		image.resize((size, size), Image.LANCZOS).save(path)
		print(path)


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

	def draw(path, symbol, size, colour, filled=False):
		big = size * SUPERSAMPLE
		font = ImageFont.truetype(font_path, big)
		font.set_variation_by_axes([1 if filled else 0, 0, 48, 400])  # outlined unless filled, regular weight
		image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
		ImageDraw.Draw(image).text((big / 2.0, big / 2.0), chr(int(codepoints[symbol], 16)), font=font, fill=_rgba(colour), anchor="mm")
		image.resize((size, size), Image.LANCZOS).save(path)
		print(path)

	for size in ICON_SIZES:
		for name, symbol in sorted(ICONS.items()):
			draw(os.path.join(out, "%s_%d.png" % (name, size)), symbol, size, theme.TEXT)
		for name in ON_LIGHT:
			draw(os.path.join(out, "%s_on_light_%d.png" % (name, size)), ICONS[name], size, theme.TEXT_ON_SELECTED)
	for size in CARD_SIZES:
		for name, symbol in sorted(CARD_ICONS.items()):
			draw(os.path.join(out, "%s_%d.png" % (name, size)), symbol, size, theme.TEXT)
			draw(os.path.join(out, "%s_on_light_%d.png" % (name, size)), symbol, size, theme.TEXT_ON_SELECTED)
	for size in KEY_SIZES:
		for name, colour in sorted(KEY_COLOURS.items()):
			draw(os.path.join(out, "key_%s_%d.png" % (name, size)), "circle", size, colour, filled=True)


if __name__ == "__main__":
	if not os.environ.get("MATERIAL") or not os.environ.get("MDI") or not os.environ.get("REC_FONT"):
		sys.exit("Set MATERIAL and MDI to the icon font folders and REC_FONT to a bold font; see the notes above ICONS, MDI_CARD_ICONS and PILL.")
	material_icons(os.environ["MATERIAL"], os.path.join(OUT, "icons"))
	mdi_icons(os.environ["MDI"], os.path.join(OUT, "icons"))
	pills(os.path.join(OUT, "icons"), os.environ["REC_FONT"])
