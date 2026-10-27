# -*- coding: utf-8 -*-
"""Fit Gullion TV's 1920x1080 layouts to whatever size the box's skin draws at.

Every screen is designed at 1920x1080. Skins draw their menus at their own size
(MetrixHD and the default skin at 1280x720, some at 720x576), so positions,
sizes and font sizes are multiplied by the skin's width / 1920: two-thirds on a
1280x720 skin. skin() does that for a screen's skin text; px() for numbers the
code uses directly (the guide grid, picture sizes).
"""
import re

DESIGN_WIDTH = 1920
_factor = []


def factor():
	"""The skin's width over the design width, worked out once from the box's screen."""
	if not _factor:
		try:
			from enigma import getDesktop
			_factor.append(getDesktop(0).size().width() / float(DESIGN_WIDTH))
		except Exception:
			_factor.append(1.0)
	return _factor[0]


def set_factor(value):
	"""For tools/check.py and tools/preview.py: pretend the skin is a given size."""
	del _factor[:]
	_factor.append(value)


def px(value):
	"""A design-size number scaled to the skin. Anything above zero stays at least 1."""
	scaled = int(round(value * factor()))
	return max(1, scaled) if value > 0 else scaled


_PAIR = re.compile(r'\b(position|size)="([^"]*)"')
_FONT = re.compile(r'\bfont="([^";]+);(\d+)"')
_NUMBER = re.compile(r'\b(itemHeight|borderWidth)="(\d+)"')


def _pair(match):
	parts = []
	for part in match.group(2).split(","):
		part = part.strip()
		parts.append(str(px(int(part))) if re.match(r"^-?\d+$", part) else part)  # leave "center" alone
	return '%s="%s"' % (match.group(1), ",".join(parts))


def skin(text):
	"""A screen's skin with every position, size, font size, item height and border scaled."""
	if factor() == 1.0:
		return text
	text = _PAIR.sub(_pair, text)
	text = _FONT.sub(lambda match: 'font="%s;%d"' % (match.group(1), px(int(match.group(2)))), text)
	return _NUMBER.sub(lambda match: '%s="%d"' % (match.group(1), px(int(match.group(2)))), text)
