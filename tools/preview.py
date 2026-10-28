# -*- coding: utf-8 -*-
"""Render sample screenshots of the GullionTV screens without a box.

Reads each screen's real skin XML, drives the screen with sample data through
the stub enigma2 modules, and draws the result at 1920x1080. Fonts and the
live TV picture are approximations; use scripts/deploy.sh for the real thing.

	pip install pillow
	python3 tools/preview.py            # writes docs/images/*.png
"""
import os
import time
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

import io
import tempfile

import e2stubs
import sample_epg
import sample_webcams

e2stubs.install()
from GullionTV import home, watchagain  # noqa: E402
from GullionTV.recordings import screen as recscreen  # noqa: E402
from GullionTV.plex import client as plex, library as plexlibrary, setup as plexsetup  # noqa: E402
from GullionTV.tv import converter, epg, guide, infobar, nowinfo, picon, serviceinfo, soundsubs  # noqa: E402
from GullionTV.ui import icons as ui_icons, pin, placeholder, popups  # noqa: E402
from GullionTV.webcams import screens as webcams, sources  # noqa: E402
from GullionTV.weather import forecast  # noqa: E402
import sample_plex  # noqa: E402

sample_epg.install()
# A recording drive with plenty of room, unless a render says otherwise.
watchagain.recordings.DEFAULT_FOLDER = tempfile.mkdtemp()
watchagain.recordings.mount_point = lambda path: "/media/hdd"
watchagain.recordings.free_space = lambda path: 500 * watchagain.recordings.GB
_names = dict((channel.ref, channel.name) for _, _, channels in epg.channel_lists() for channel in channels)
e2stubs.SERVICE_NAMES.update(_names)
_picons = {}


def sample_picon(ref):
	"""A stand-in picon file: the channel name on a light card, like the real logos' backgrounds."""
	name = _names.get(ref)
	if not name:
		return None
	if ref not in _picons:
		card = Image.new("RGB", (220, 132), (236, 234, 228))
		draw_text(ImageDraw.Draw(card), (8, 0, 204, 132), name, {"font": "Regular;34", "halign": "center", "valign": "center"}, (17, 19, 22))
		_picons[ref] = os.path.join(tempfile.mkdtemp(), "picon.png")
		card.save(_picons[ref])
	return _picons[ref]


picon.picon_path = sample_picon

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "docs", "images")
WIDTH, HEIGHT = 1920, 1080
FONT_FILE = "/System/Library/Fonts/HelveticaNeue.ttc"

NOW = sample_epg.NOW
SEVEN_PM = NOW - 42 * 60
time.time = lambda: NOW

_fonts = {}


def font(size):
	if size not in _fonts:
		try:
			_fonts[size] = ImageFont.truetype(FONT_FILE, size)
		except OSError:
			_fonts[size] = ImageFont.load_default(size)
	return _fonts[size]


def parse_colour(value):
	"""#AARRGGBB (AA=00 opaque) or an int from gRGB(). None if fully transparent."""
	if value is None:
		return None
	if isinstance(value, int):
		argb = value
	else:
		argb = int(value.lstrip("#"), 16)
	if argb >> 24 == 0xff:
		return None
	return ((argb >> 16) & 0xff, (argb >> 8) & 0xff, argb & 0xff)


def pair(value, parent_size, own_size=(0, 0)):
	parts = value.split(",")
	result = []
	for i, part in enumerate(parts):
		if part == "center":
			result.append((parent_size[i] - own_size[i]) // 2)
		else:
			result.append(int(part))
	return tuple(result)


def wrap(text, face, width):
	lines = []
	for paragraph in text.split("\n"):
		stripped = paragraph.lstrip(" ")
		indent = paragraph[:len(paragraph) - len(stripped)]
		paragraph = stripped
		line = indent
		for word in paragraph.split(" "):
			candidate = word if not line.strip() else line + " " + word
			if not line.strip():
				candidate = line + word
			if face.getlength(candidate) <= width or not line.strip():
				line = candidate
			else:
				lines.append(line)
				line = word
		lines.append(line)
	return lines


def draw_text(draw, box, text, attrs, colour):
	if not text or colour is None:
		return
	x, y, w, h = box
	size = int(attrs.get("font", "Regular;20").split(";")[1])
	face = font(size)
	line_height = int(size * 1.22)
	lines = wrap(text, face, w)
	lines = lines[:max(1, h // line_height)]
	total = line_height * len(lines)
	valign = attrs.get("valign", "top")
	top = y + {"top": 0, "center": (h - total) // 2, "bottom": h - total}[valign]
	for i, line in enumerate(lines):
		halign = attrs.get("halign", "left")
		left = x + {"left": 0, "center": (w - face.getlength(line)) / 2, "right": w - face.getlength(line)}[halign]
		draw.text((left, top + i * line_height), line, font=face, fill=colour)


def draw_list(image, box, widget):
	"""eListboxPythonMultiContent rows: each entry is a positioned text cell."""
	x, y, w, h = box
	height = widget.l.item_height
	for row, entries in enumerate(widget.list):
		top = y + row * height
		if top >= y + h:
			break
		for entry in entries[1:]:
			ex, ey = entry["pos"]
			ew, eh = entry["size"]
			if "png" in entry:
				icon = Image.open(entry["png"]).convert("RGBA").resize((ew, eh))
				image.paste(icon, (x + ex, top + ey), icon)
				continue
			cell = Image.new("RGB", (ew, eh), parse_colour(entry["backcolor"]) or (0, 0, 0))
			cell_draw = ImageDraw.Draw(cell)
			text = entry.get("text") or ""
			if text:
				face = font(widget.l.fonts.get(entry.get("font", 0), 28))
				flags = entry.get("flags", 0)
				tw = face.getlength(text)
				tx = {0: 0, 1: ew - tw, 2: (ew - tw) / 2}[flags & 3]
				ascent, descent = face.getmetrics()
				ty = (eh - ascent - descent) / 2 if flags & 4 else 0
				cell_draw.text((tx, ty), text, font=face, fill=parse_colour(entry["color"]))
			image.paste(cell, (x + ex, top + ey))


def paste_fitted(image, box, path):
	"""Like ePicLoad with keep-aspect: scale to fit, letterboxed on the card colour."""
	x, y, w, h = box
	picture = Image.open(path).convert("RGB")
	scale = min(w / float(picture.width), h / float(picture.height))
	picture = picture.resize((max(1, int(picture.width * scale)), max(1, int(picture.height * scale))), Image.LANCZOS)
	backdrop = Image.new("RGB", (w, h), parse_colour(guide.theme.CARD))
	backdrop.paste(picture, ((w - picture.width) // 2, (h - picture.height) // 2))
	image.paste(backdrop, (x, y))


def scene(kind, w=640, h=360):
	"""Flat placeholder pictures for the sample webcams."""
	picture = Image.new("RGB", (w, h))
	d = ImageDraw.Draw(picture)
	for row in range(h):
		t = row / float(h)
		d.line([(0, row), (w, row)], fill=(int(120 + 60 * t), int(150 + 50 * t), int(190 + 30 * t)))
	stone, dark, green, water = (150, 140, 128), (70, 66, 62), (88, 120, 76), (60, 96, 130)
	if kind in ("church", "cathedral"):
		d.rectangle((0, h * 0.78, w, h), fill=green)
		d.rectangle((w * 0.3, h * 0.42, w * 0.72, h * 0.8), fill=stone)
		d.polygon([(w * 0.28, h * 0.44), (w * 0.51, h * 0.22), (w * 0.74, h * 0.44)], fill=dark)
		towers = [0.2, 0.76] if kind == "cathedral" else [0.18]
		for left in towers:
			d.rectangle((w * left, h * 0.25, w * (left + 0.1), h * 0.8), fill=stone)
			d.polygon([(w * left, h * 0.26), (w * (left + 0.05), h * 0.06), (w * (left + 0.1), h * 0.26)], fill=dark)
		d.rounded_rectangle((w * 0.47, h * 0.6, w * 0.55, h * 0.8), 12, fill=dark)
	elif kind == "street":
		d.rectangle((0, h * 0.8, w, h), fill=(90, 90, 92))
		colours = [(176, 120, 96), (210, 196, 160), (120, 140, 160), (190, 170, 120), (150, 110, 110)]
		for i, colour in enumerate(colours):
			d.rectangle((i * w / 5.0, h * (0.35 + 0.05 * (i % 2)), (i + 1) * w / 5.0 - 6, h * 0.8), fill=colour)
	elif kind == "harbour":
		d.rectangle((0, h * 0.6, w, h), fill=water)
		d.polygon([(w * 0.35, h * 0.62), (w * 0.62, h * 0.62), (w * 0.57, h * 0.72), (w * 0.4, h * 0.72)], fill=(200, 80, 60))
		d.line([(w * 0.48, h * 0.62), (w * 0.48, h * 0.3)], fill=dark, width=6)
	elif kind == "studio":
		d.rectangle((0, 0, w, h), fill=(54, 44, 60))
		d.rectangle((0, h * 0.7, w, h), fill=(110, 80, 60))
		d.ellipse((w * 0.36, h * 0.2, w * 0.5, h * 0.45), fill=(196, 150, 120))
		d.rounded_rectangle((w * 0.3, h * 0.42, w * 0.56, h * 0.9), 20, fill=(40, 70, 110))
		d.rectangle((w * 0.65, h * 0.15, w * 0.92, h * 0.6), fill=(90, 120, 160))
	elif kind == "kitchen":
		d.rectangle((0, 0, w, h), fill=(200, 196, 186))
		d.rectangle((0, h * 0.62, w, h), fill=(120, 120, 126))
		for left in (0.1, 0.45, 0.75):
			d.ellipse((w * left, h * 0.5, w * (left + 0.16), h * 0.66), fill=(70, 70, 74))
		d.ellipse((w * 0.5, h * 0.14, w * 0.62, h * 0.36), fill=(190, 140, 110))
	elif kind == "bridge":
		d.rectangle((0, h * 0.66, w, h), fill=water)
		d.rectangle((0, h * 0.5, w, h * 0.56), fill=stone)
		for left in (0.1, 0.4, 0.7):
			d.pieslice((w * left, h * 0.5, w * (left + 0.2), h * 0.8), 180, 360, fill=stone)
	return picture


def poster_bytes(title, size=(400, 600)):
	"""A stand-in film or programme poster: a block of colour with the title."""
	w, h = size
	shade = sum(map(ord, title))
	colours = [(122, 52, 44), (36, 70, 102), (46, 92, 70), (96, 68, 120), (140, 96, 40), (60, 60, 66)]
	base = colours[shade % len(colours)]
	poster = Image.new("RGB", size)
	d = ImageDraw.Draw(poster)
	for row in range(h):
		t = row / float(h)
		d.line([(0, row), (w, row)], fill=tuple(int(c * (1.15 - 0.5 * t)) for c in base))
	d.ellipse((w * 0.2, h * 0.16, w * 0.8, h * 0.56), fill=tuple(min(255, int(c * 1.5)) for c in base))
	draw_text(d, (24, int(h * 0.62), w - 48, int(h * 0.34)), title.upper(), {"font": "Regular;44", "halign": "center"}, (245, 240, 230))
	buffer = io.BytesIO()
	poster.save(buffer, "JPEG", quality=88)
	return buffer.getvalue()


def picture_bytes(kind, size=(640, 360)):
	buffer = io.BytesIO()
	scene(kind, *size).save(buffer, "JPEG", quality=88)
	return buffer.getvalue()


def draw_picture(image, box, label):
	"""Stand-in for the live TV picture: a dim studio-like scene."""
	x, y, w, h = box
	scene = Image.new("RGB", (w, h))
	px = ImageDraw.Draw(scene)
	for row in range(h):
		shade = row / float(h)
		px.line([(0, row), (w, row)], fill=(int(48 - 22 * shade), int(62 - 26 * shade), int(84 - 30 * shade)))
	px.ellipse((w * 0.55, h * 0.18, w * 0.75, h * 0.52), fill=(120, 96, 84))
	px.rounded_rectangle((w * 0.46, h * 0.48, w * 0.84, h * 1.1), 40, fill=(38, 44, 60))
	px.rectangle((0, h * 0.78, w, h), fill=(24, 28, 36))
	px.text((w * 0.06, h * 0.12), label, font=font(30), fill=(160, 168, 180))
	image.paste(scene, (x, y))


class Banner(dict):
	"""The channel banner has no screen code of its own: everything comes from sources."""
	skin = infobar.SKIN


def resolve(el, state):
	"""What a source widget would show: (visible, text, progress)."""
	source = el.get("source")
	converts = [(c.get("type"), (c.text or "").strip()) for c in el.findall("convert")]
	event = state.get({"session.Event_Now": "now", "session.Event_Next": "next"}.get(source))
	text, value, visible = el.get("text", ""), 0, True
	for kind, arg in converts:
		if kind == "GullionServiceInfo":
			c = converter.GullionServiceInfo(arg)
			if arg == "IsRecording":
				visible = state.get("recording", False)
				continue
			if arg.startswith("Icon:"):
				# The banner's icon row: the programme's codes, then hd, then how it arrives.
				names = serviceinfo.icon_row(state["ref"], state.get("height", 1080), state.get("description", ""))
				position = int(arg.split(":")[1])
				text = names[-position] if position <= len(names) else ""
				visible = bool(text)
				continue
			if arg == "Remaining":
				c.source = e2stubs.types.SimpleNamespace(event=e2stubs.types.SimpleNamespace(
					getBeginTime=lambda: event[0], getDuration=lambda: event[1]))
			else:
				c.source = e2stubs.fake_service(state["ref"], state.get("height", -1), state["name"])
			text = c.text
		elif kind == "ServiceName":
			text = state["name"]
		elif kind == "FrontendInfo":
			text, value = "%d %%" % state["snr"], state["snr"]
		elif kind == "EventName":
			text = event[2]
		elif kind == "EventTime" and arg == "StartTime":
			text = event[0]
		elif kind == "EventTime" and arg == "Progress":
			value = int((NOW - event[0]) * 100 / event[1])
		elif kind == "ClockToText":
			fmt = arg.split("Format:", 1)[1] if "Format:" in arg else "%H:%M"
			text = time.strftime(fmt, time.localtime(text if isinstance(text, (int, float)) else NOW))
		elif kind == "ConditionalShowHide" and source == "session.RecordState":
			visible = state.get("recording", False)
	return visible, text, value


def draw_picon(draw, box, name):
	"""Stand-in for a channel logo picon."""
	x, y, w, h = box
	draw.rounded_rectangle((x, y, x + w - 1, y + h - 1), 10, fill=(236, 234, 228))
	draw_text(draw, (x + 8, y, w - 16, h), name, {"font": "Regular;34", "halign": "center", "valign": "center"}, (17, 19, 22))


def render(screen, base=None, state=None):
	root = ET.fromstring(screen.skin)
	size = pair(root.get("size"), (WIDTH, HEIGHT))
	origin = pair(root.get("position"), (WIDTH, HEIGHT), size)
	image = base.copy() if base is not None else Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
	draw = ImageDraw.Draw(image)
	draw.rectangle((origin[0], origin[1], origin[0] + size[0] - 1, origin[1] + size[1] - 1),
		fill=parse_colour(root.get("backgroundColor")))

	elements = sorted(list(root), key=lambda el: int(el.get("zPosition", "0")))
	for el in elements:
		if el.tag not in ("eLabel", "widget", "ePixmap") or el.get("position") is None:
			continue
		w, h = pair(el.get("size"), size)
		x, y = pair(el.get("position"), size, (w, h))
		box = (origin[0] + x, origin[1] + y, w, h)
		if el.tag == "ePixmap":
			icon = Image.open(el.get("pixmap")).convert("RGBA").resize((w, h), Image.LANCZOS)
			image.paste(icon, box[:2], icon)
			continue
		widget = screen.get(el.get("name")) if el.get("name") else None
		instance = widget.instance if widget is not None else None
		if widget is not None and not getattr(widget, "visible", True):
			continue
		if instance is not None and getattr(instance, "position", None):
			box = (origin[0] + instance.position[0], origin[1] + instance.position[1], w, h)
		if isinstance(widget, e2stubs.Pixmap):
			pixmap = getattr(instance, "pixmap", None)
			if pixmap and pixmap.startswith("sample:"):
				draw_picon(draw, box, pixmap.split(":", 1)[1])
			elif pixmap and os.path.isfile(pixmap) and el.get("alphatest") == "blend":
				icon = Image.open(pixmap).convert("RGBA").resize((w, h), Image.LANCZOS)
				image.paste(icon, (box[0], box[1]), icon)  # drawn straight over what's behind
			elif pixmap and os.path.isfile(pixmap):
				paste_fitted(image, box, pixmap)
			continue
		if isinstance(widget, e2stubs.MenuList):
			draw_list(image, box, widget)
			continue

		background = parse_colour(el.get("backgroundColor"))
		foreground = parse_colour(el.get("foregroundColor") or "#00ffffff")
		if instance is not None and instance.background is not None:
			background = parse_colour(instance.background)
		if instance is not None and instance.foreground is not None:
			foreground = parse_colour(instance.foreground)

		source = el.get("source")
		if state is not None and source and source.startswith("session.") and source != "session.VideoPicture":
			visible, text, value = resolve(el, state)
			if not visible:
				continue
			if el.get("render") == "Picon":
				draw_picon(draw, box, state["name"])
				continue
			if el.get("render") == "Pixmap":
				picture = Image.open(el.get("pixmap")).convert("RGBA").resize((w, h), Image.LANCZOS)
				image.paste(picture, box[:2], picture)
				continue
			if el.get("render") == "GullionIcon":
				icon = Image.open(ui_icons.icon_path(text)).convert("RGBA").resize((w, h), Image.LANCZOS)
				image.paste(icon, box[:2], icon)
				continue
			if background is not None and el.get("transparent") != "1":
				draw.rectangle((box[0], box[1], box[0] + w - 1, box[1] + h - 1), fill=background)
			if el.get("render") == "Progress":
				draw.rectangle((box[0], box[1], box[0] + int(w * value / 100.0) - 1, box[1] + h - 1), fill=foreground)
				continue
			draw_text(draw, box, text, el.attrib, foreground)
			continue
		if source == "session.VideoPicture":
			draw_picture(image, box, "Sample picture")
			continue
		if background is not None and el.get("transparent") != "1":
			draw.rectangle((box[0], box[1], box[0] + w - 1, box[1] + h - 1), fill=background)
		if (el.get("name") or "").endswith("progress") and widget is not None:
			filled = int(w * widget.value / 100.0)
			draw.rectangle((box[0], box[1], box[0] + filled - 1, box[1] + h - 1), fill=foreground)
			continue

		if source == "global.CurrentTime":
			convert = el.find("convert")
			fmt = convert.text.split("Format:", 1)[1] if convert is not None and "Format:" in convert.text else "%H:%M"
			text = time.strftime(fmt, time.localtime(NOW))
		elif widget is not None:
			text = widget.text
		else:
			text = el.get("text", "")
		draw_text(draw, box, text, el.attrib, foreground)
	return image


def home_screen(selected=0):
	# A sample report already fetched, so Home shows its weather line.
	e2stubs.config.plugins.gulliontv.weather_location.value = "54.0830, -6.4500"
	forecast.remember((54.083, -6.45), forecast.Report(8, "Light rain", 14, "tomorrow", "Met Éireann", fetched_at=NOW,
		icon=forecast.symbol_icon("LightRain", daytime=False)))
	session = e2stubs.fake_session(
		channel="RTÉ One",
		now=(SEVEN_PM, 3600, "Nationwide"),
		upcoming=(SEVEN_PM + 3600, 1800, "Fair City"),
	)
	screen = home.GullionHome(session)
	screen.layout()
	screen.refresh()
	screen.move_to(selected)
	return screen


def main():
	if not os.path.isdir(OUT):
		os.makedirs(OUT)
	shots = []

	shots.append(("01-home-watch-tv", render(home_screen(0))))
	shots.append(("02-home-webcams", render(home_screen(3))))
	settings_home = render(home_screen(home.SETTINGS))
	shots.append(("03-home-settings", settings_home))

	prompt = pin.TechSupportPin(e2stubs.fake_session())
	prompt.digit(4)
	prompt.digit(7)
	shots.append(("04-techsupport-pin", render(prompt, settings_home)))

	e2stubs.config.plugins.gulliontv.pin.value = 1234
	prompt = pin.TechSupportPin(e2stubs.fake_session())
	for digit in (4, 7, 1, 1):
		prompt.digit(digit)
	shots.append(("05-techsupport-pin-wrong", render(prompt, settings_home)))

	choose = pin.PinEntry(e2stubs.fake_session(), "Choose a Tech Support PIN",
		"This is the first time Settings has been opened. Choose a 4-digit PIN for Tech Support.")
	choose.layout()
	for digit in (4, 8):
		choose.digit(digit)
	shots.append(("05b-techsupport-choose-pin", render(choose, settings_home)))

	shots.append(("06-coming-soon", render(placeholder.ComingSoon(e2stubs.fake_session(), "Recordings"))))

	tv_guide = guide.Guide(e2stubs.fake_session())
	tv_guide.layout()
	shots.append(("07-guide-now", render(tv_guide)))
	selector = guide.ChannelLists(e2stubs.fake_session(), [(item[1], i) for i, item in enumerate(tv_guide.lists)], tv_guide.list_index)
	selector.layout()
	shots.append(("07b-guide-channel-lists", render(selector, render(tv_guide))))
	# Show a numbering gap at a bouquet boundary without changing the other samples.
	original_lists = guide.epg.channel_lists
	try:
		channels = tv_guide.channels[:8]
		guide.epg.channel_lists = lambda: [
			("saor", "Saorview", [guide.epg.Channel(c.ref, c.name, 17 + i) for i, c in enumerate(channels[:4])]),
			("free", "Freesat", [guide.epg.Channel(c.ref, c.name, 101 + i) for i, c in enumerate(channels[4:])])]
		boundary = guide.Guide(e2stubs.fake_session())
		boundary.layout()
		boundary.move_row(3)
		shots.append(("07c-guide-bouquet-boundary", render(boundary)))
	finally:
		guide.epg.channel_lists = original_lists

	tv_guide.next_event()
	shots.append(("08-guide-will-record", render(tv_guide)))

	tv_guide.move_row(4)
	tv_guide.next_event()
	choice_base = render(tv_guide)
	shots.append(("09-guide-bbc-one", choice_base))
	event = tv_guide.selected_event()
	choice = popups.GullionChoice(e2stubs.fake_session(), event.title, [("Record this", "record"), ("Cancel", None)], tv_guide.when(event))
	choice.layout()
	shots.append(("10-guide-record-choice", render(choice, choice_base)))

	tv_guide = guide.Guide(e2stubs.fake_session())
	tv_guide.layout()
	event = tv_guide.selected_event()
	details = popups.EventDetails(e2stubs.fake_session(), event.title, tv_guide.when(event), event.description + " (HD, S, A, R)", tv_guide.channels[tv_guide.row].ref)
	details.layout()
	shots.append(("11-guide-details", render(details, render(tv_guide))))

	tv_guide.shift_day(1)
	tv_guide.list_chosen(1)
	shots.append(("12-guide-saorview-tomorrow", render(tv_guide)))

	banners = [
		("13-banner-terrestrial", {"ref": "1:0:19:1:1:1:EEEE0000:0:0:0:", "name": "RTÉ One", "snr": 82,
			"description": "The stories that matter from around the country. (HD, S)", "now": (SEVEN_PM, 3600, "Nationwide"), "next": (SEVEN_PM + 3600, 1800, "Fair City")}),
		("14-banner-satellite-recording", {"ref": "1:0:19:5:1:1:11A0000:0:0:0:", "name": "BBC One NI", "snr": 71,
			"description": "Drama in Walford. [S,AD] [HD]",
			"recording": True, "now": (SEVEN_PM + 1800, 1800, "EastEnders"), "next": (SEVEN_PM + 3600, 3600, "MasterChef")}),
		("15-banner-sd", {"ref": "1:0:19:4:1:1:EEEE0000:0:0:0:", "name": "TG4", "snr": 64, "height": 576,
			"now": (SEVEN_PM + 1200, 2400, "Ros na Rún"), "next": (SEVEN_PM + 3600, 3600, "Seó Spóirt")}),
	]
	tv = Image.new("RGB", (WIDTH, HEIGHT))
	draw_picture(tv, (0, 0, WIDTH, HEIGHT), "")
	for name, state in banners:
		shots.append((name, render(Banner(), tv, state)))

	# INFO (or OK twice) on live TV, with a satellite tuner's details.
	status = {"tuner_signal_quality": 58000, "tuner_signal_quality_db": 1240, "tuner_signal_power": 47000,
		"tuner_bit_error_rate": 0, "tuner_number": 0}
	transponder = {"tuner_type": "DVB-S", "frequency": 10773000, "polarization": 0, "symbol_rate": 22000000}
	frontend = e2stubs.types.SimpleNamespace(getFrontendStatus=lambda: status, getTransponderData=lambda original: transponder)
	info_session = e2stubs.fake_session()
	service = info_session.nav.getCurrentService()
	service.frontendInfo = lambda: frontend
	info = nowinfo.ChannelInfo(info_session)
	info.ref = epg.channel_lists()[0][2][0].ref
	info.layout()
	info.draw_icons("The stories that matter from around the country. (HD, S, AD)")
	shots.append(("15b-whats-on", render(info, tv)))

	# YELLOW on live TV: sound tracks and subtitles.
	tracks = [("eng", "MPEG"), ("NAR", "MPEG"), ("eng", "AC3")]
	audio = e2stubs.types.SimpleNamespace(getNumberOfTracks=lambda: len(tracks), getCurrentTrack=lambda: 0,
		getTrackInfo=lambda i: e2stubs.types.SimpleNamespace(getLanguage=lambda: tracks[i][0], getDescription=lambda: tracks[i][1]))
	sound_session = e2stubs.fake_session()
	sound_session.nav.getCurrentService().audioTracks = lambda: audio
	subtitles = [(0, 1234, 0, 0, "eng"), (1, 0, 888, 8, "eng")]
	watching = e2stubs.types.SimpleNamespace(selected_subtitle=None,
		getCurrentServiceSubtitle=lambda: e2stubs.types.SimpleNamespace(getSubtitleList=lambda: subtitles))
	sound = soundsubs.SoundAndSubtitles(sound_session, watching)
	sound.layout()
	shots.append(("15c-sound-and-subtitles", render(sound, tv)))

	# Typing a channel number.
	class Popup(dict):
		def __init__(self, skin, **texts):
			dict.__init__(self)
			self.skin = skin
			for name, text in texts.items():
				self[name] = e2stubs.Widget(text)
	shots.append(("15d-channel-number", render(Popup(infobar.NUMBER_ZAP, number="101", servicename="BBC One NI HD"), tv)))

	sample_webcams.PICTURES.update({
		"https://cdn.example/live/Uploads/ProfileImages/stmalachys.jpeg": picture_bytes("church"),
		"https://www.churchservices.tv/wp-content/uploads/cathedral-225x300.jpg": picture_bytes("cathedral", (225, 300)),
		"http://cams.example/main-street.jpg": picture_bytes("street"),
	})
	sample_webcams.CONFIG_WITH_PICTURES = sample_webcams.CONFIG.replace(
		"    url: https://quiet.example/bridge/live.m3u8\n", "    url: https://quiet.example/bridge/live.m3u8\n    image: http://cams.example/bridge.jpg\n")
	sample_webcams.PICTURES["http://cams.example/bridge.jpg"] = picture_bytes("bridge")
	sources.fetch = sample_webcams.fake_fetch
	sources.THUMB_DIR = tempfile.mkdtemp()
	config_file = os.path.join(sources.THUMB_DIR, "webcams.yaml")
	with open(config_file, "w") as handle:
		handle.write(sample_webcams.CONFIG_WITH_PICTURES)
	session = e2stubs.fake_session()
	grid = webcams.WebcamList(session, config_file)
	grid.layout()
	grid.worker.join(5)
	grid.repaint_if_changed()
	shots.append(("16-webcams", render(grid)))

	grid.move(1)
	grid.move(webcams.COLS)
	offline = render(grid)
	cam = grid.webcams[grid.selected]
	choice = popups.GullionChoice(session, cam.name, [("Try anyway", "play"), ("Back", None)], "This camera isn't live right now.")
	choice.layout()
	shots.append(("17-webcams-not-live", render(choice, offline)))

	player = webcams.WebcamPlayer(session, grid.webcams[0])
	player.layout()
	session.picture["height"] = 720
	player.check_picture()
	full = Image.new("RGB", (WIDTH, HEIGHT))
	full.paste(scene("church", WIDTH, HEIGHT), (0, 0))
	shots.append(("18-webcam-playing", render(player, full)))

	empty = webcams.WebcamList(session, "/nonexistent/webcams.yaml")
	empty.layout()
	shots.append(("19-webcams-empty", render(empty)))

	# Watch again, with recorded TV and Plex.
	folder = sample_plex.make_recordings(os.path.join(tempfile.mkdtemp(), "movie"))
	watchagain.recordings.DEFAULT_FOLDER = folder
	# As if ffmpeg had already made frames for the three newest recordings.
	for recording, kind in zip(watchagain.recordings.list_recordings(folder)[:3], ("studio", "kitchen", "street")):
		scene(kind, 768, 432).save(recording.path + ".jpg", quality=88)
	plex.http_request = sample_plex.FakePlex("home")
	titles = {}
	for item in (sample_plex.CONTINUE + sample_plex.RECENT_FILMS + sample_plex.RECENT_TV
			+ sample_plex.LIBRARY_FILMS + sample_plex.LIBRARY_TV):
		titles[item["ratingKey"]] = item.get("grandparentTitle") or item["title"]
		if item.get("grandparentThumb"):
			titles[item["grandparentThumb"].split("/")[3]] = item["grandparentTitle"]
	kinds = ("harbour", "street", "bridge", "church", "cathedral")

	def plex_picture(url, binary=False, timeout=8):
		"""Landscape scenes for art and stills; a placeholder poster with the title for posters."""
		try:
			from urllib.parse import parse_qs, urlparse
		except ImportError:
			from urlparse import parse_qs, urlparse
		path = parse_qs(urlparse(url).query)["url"][0]
		key = path.split("/")[3]
		if path.endswith("/thumb"):
			return poster_bytes(titles.get(key, key))
		return picture_bytes(kinds[sum(map(ord, key)) % len(kinds)])

	sources.fetch = plex_picture
	watchagain.PLEX_THUMBS = tempfile.mkdtemp()
	session = e2stubs.fake_session()
	again = watchagain.WatchAgain(session, sample_plex.configured_settings())
	again.layout()
	again.background.wait()
	again.paint()
	shots.append(("20-watch-again", render(again)))
	again.choose_filter(2)
	again.move_down(1)
	shots.append(("21-watch-again-browse", render(again)))

	# Recordings: what Watch again opens without Plex.
	listing = recscreen.Recordings(session)
	listing.layout()
	listing.background.wait()
	listing_shot = render(listing)
	shots.append(("22-recordings", listing_shot))
	options = popups.GullionChoice(session, "Fair City", [("Watch from the start", "start"), ("Delete", "delete"), ("Cancel", None)],
		"%s  ·  %s" % (recscreen.short_when(listing.chosen()), watchagain.recordings.file_size(listing.chosen().size)))
	options.layout()
	shots.append(("22b-recordings-options", render(options, listing_shot)))
	session.nav.RecordTimer = e2stubs.types.SimpleNamespace(timer_list=[e2stubs.types.SimpleNamespace(state=2, Filename=listing.recordings[1].path[:-3])])
	listing.move(1)
	shots.append(("22c-recordings-recording-now", render(listing)))
	del session.nav.RecordTimer
	listing.move(2)
	listing.change_order()
	listing.change_order()
	no_picture = render(listing)
	shots.append(("23-recordings-a-to-z-no-picture", no_picture))
	ask = popups.GullionChoice(session, "Delete %s?" % listing.chosen().title, [("Delete", "delete"), ("Keep it", None)],
		"It goes to the recycle bin, so Tech Support can bring it back.")
	ask.layout()
	shots.append(("24-delete-recording", render(ask, no_picture)))

	from GullionTV.recordings import player as recplayer
	play_session = e2stubs.fake_session()
	play_service = e2stubs.PlaybackService(position=720, length=1800)
	play_session.nav.getCurrentService = lambda: play_service
	recording = watchagain.recordings.list_recordings(folder)[0]
	playback = recplayer.RecordingPlayer(play_session, e2stubs.eServiceReference(recording.service_ref), recording)
	playback.layout()
	picture = scene("studio", 1920, 1080)
	shots.append(("24b-recording-playing", render(playback, picture)))
	playback.select_progress()
	shots.append(("24f-recording-scrubbing", render(playback, picture)))
	playback.select_controls()
	playback.toggle_pause()
	shots.append(("24c-recording-paused", render(playback, picture)))
	playback.play()
	play_service.tracks = []
	playback.refresh_playback()
	shots.append(("24d-recording-no-subtitles", render(playback, picture)))
	play_service.tracks = [(0, 101, 0, 0, "eng")]
	subtitle_choices = soundsubs.SoundAndSubtitles(play_session, playback, focus="subtitles")
	subtitle_choices.layout()
	shots.append(("24e-recording-subtitles", render(subtitle_choices, picture)))
	playback.cleanup()


	original_load = plex.load_settings
	plex.load_settings = lambda path=None: sample_plex.configured_settings()
	plex.load_settings = original_load

	# Tech Support's Plex setup.
	settings_file = os.path.join(tempfile.mkdtemp(), "plex.json")
	plex.save_settings(dict(sample_plex.configured_settings(), last_uri=sample_plex.REMOTE), settings_file)
	setup_screen = plexsetup.PlexSetup(session, settings_file, sample_plex.FakePlex("away"))
	setup_screen.layout()
	setup_screen.move(3)
	shots.append(("26-plex-setup", render(setup_screen)))

	link = plexsetup.PlexLink(session, plex.Client(plex.load_settings(settings_file), sample_plex.FakePlex()))
	link.layout()
	link.background.wait()
	shots.append(("27-plex-link", render(link, render(setup_screen))))

	users = plexsetup.OptionList(session, "Who does the TV watch as?", [("Alex", 0, "Admin"), ("Sam", 1, "PIN")],
		"The TV always uses this person's Plex: their films, programmes and what they've watched.")
	users.layout()
	users.move(1)
	shots.append(("28-plex-user", render(users, render(setup_screen))))

	libraries = plexsetup.OptionList(session, "Choose the libraries", [("Films", "1", ""), ("TV Programmes", "2", "")],
		"Only film and TV libraries are shown.", toggles=["1", "2"])
	libraries.layout()
	shots.append(("29-plex-libraries", render(libraries, render(setup_screen))))

	drive = watchagain.recordings
	drive.mount_point = lambda path: "/"
	no_drive = guide.Guide(e2stubs.fake_session())
	no_drive.layout()
	base = render(no_drive)
	shots.append(("30-guide-no-recording-drive", base))
	message = popups.GullionChoice(session, "This box can't record right now", [("OK", None)], "Ask Tech Support to check the recording drive.")
	message.layout()
	shots.append(("31-guide-cannot-record", render(message, base)))
	drive.mount_point = lambda path: "/media/hdd"
	drive.free_space = lambda path: 5 * drive.GB
	low = guide.Guide(e2stubs.fake_session())
	low.layout()
	shots.append(("32-guide-low-space", render(low)))
	drive.free_space = lambda path: 500 * drive.GB

	library_session = e2stubs.fake_session()
	plexlibrary.POSTERS = tempfile.mkdtemp()
	films = plexlibrary.PlexLibrary(library_session, sample_plex.configured_settings(), plex.MOVIE, sample_plex.FakePlex())
	films.layout()
	films.background.wait()
	films.move(3)
	shots.append(("33-plex-films", render(films)))
	films.toggle_unwatched()
	films.background.wait()
	shots.append(("34-plex-films-unwatched", render(films)))
	programmes = plexlibrary.PlexLibrary(library_session, sample_plex.configured_settings(), plex.SHOW, sample_plex.FakePlex())
	programmes.layout()
	programmes.background.wait()
	programmes.move(1)
	shots.append(("35-plex-tv-programmes", render(programmes)))

	for name, image in shots:
		path = os.path.join(OUT, name + ".png")
		image.save(path)
		print(path)


if __name__ == "__main__":
	main()
